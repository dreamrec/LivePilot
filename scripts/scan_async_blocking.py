#!/usr/bin/env python3
"""AST scanner for the "blocking call on the event loop" bug class.

Finds `async def` functions in mcp_server/ that call one of the known
blocking primitives directly, one hop away through a same-file plain
`def` helper, or N hops away across files (see "Transitive detection"),
without being offloaded via `asyncio.to_thread`, `loop.run_in_executor`,
or the `send_command_async` wrapper.

Blocking primitives detected:
  - `<name>.send_command(...)`         (sync TCP client — excludes bridge/m4l)
  - `<name>.write_bytes/write_text/read_bytes/read_text/mkdir(...)` (pathlib-style file I/O)
  - `subprocess.<anything>(...)`       (subprocess module calls)

Explicitly NOT a violation:
  - `<name>.send_command_async(...)`   (the awaitable wrapper)
  - `bridge.send_command(...)` / anything with "bridge" or "m4l" in the
    dotted receiver chain (the M4L bridge is already async-native)
  - Any blocking call already wrapped by an ancestor `asyncio.to_thread(...)`
    or `<x>.run_in_executor(...)` call in the same expression tree.

Transitive detection (added 2026-07-31)
---------------------------------------
The same-file one-hop rule missed a real defect: `commit_preview_variant`
(async, preview_studio/tools.py) called `record_turn_resolution()`
(session_continuity/tracker.py), which holds a `threading.Lock` while calling
`_project_store.save_turn()` -> ... -> `base_store.write()`, whose `mkdir` /
`open` / `os.fsync` are the actual blocking primitives. Three hops, three
files. The helper index was same-file only, so nothing fired.

The fix is a project-wide fixed point rather than a hand-maintained denylist
(which would drift the moment someone adds a blocking function):

  1. Index every `def` under the scan root by simple name.
  2. Seed: a sync function is "blocking" if it directly contains a tracked
     primitive (unwrapped).
  3. Iterate to a fixed point: a sync function is blocking if it calls a
     function that is blocking.
  4. Report any `async def` that calls a blocking sync function unwrapped.

Two rules keep this sound under simple-name ambiguity (149 of 1757 names in
mcp_server/ are defined more than once):

  * A call marks its caller blocking only when **every** candidate definition
    of that name is blocking — whichever one it really resolves to, the answer
    is the same. Names like `to_dict` (157 definitions, none blocking) can
    never propagate.
  * A function is excluded from its own candidate set, which breaks the
    self-referential case where a thin wrapper delegates to a same-named
    implementation in another module (`session_continuity/tools.py` ->
    `session_continuity/tracker.py::record_turn_resolution`).

The receiver exemptions (`bridge`/`m4l`/`spectral`) apply to transitively
resolved calls too — without that, resolving `send_command` by bare name
re-flags every already-exempt `bridge.send_command(...)` call site.

Baseline
--------
Widening the rule surfaced 42 genuine pre-existing sites (8 distinct root
causes). They are recorded in `scripts/async_blocking_baseline.json` so CI
fails on NEW violations rather than on the backlog. Entries are keyed by
(file, function, target) — not line number — so they survive code movement.
Regenerate with `--update-baseline`; use `--no-baseline` to see everything.
Shrinking that file is the point; growing it should need a good reason.

Usage:
    python3 scripts/scan_async_blocking.py [root] [--exclude path1 path2 ...] [--json]
                                           [--no-baseline] [--update-baseline]

Exit code is 1 if any non-baselined violation is found (for CI), 0 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Attribute names that count as blocking file I/O when called on any receiver.
FILE_IO_ATTRS = {"write_bytes", "write_text", "read_bytes", "read_text", "mkdir"}

# Receiver-chain tokens that exempt a `.send_command(...)` call — these
# receivers are already async-native (M4L bridge / spectral cache) and must
# never be wrapped in to_thread.
EXEMPT_RECEIVER_TOKENS = {"bridge", "m4l", "spectral"}

# Call attribute names that count as "already offloaded" wrappers.
OFFLOAD_ATTRS = {"to_thread", "run_in_executor"}


def _dotted_chain_tokens(node: ast.AST) -> list[str]:
    """Return the lowercased identifier tokens in a dotted attribute/name chain.

    e.g. `self.m4l_bridge.send_command` -> ["self", "m4l_bridge", "send_command"]
    """
    tokens: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        tokens.append(cur.attr.lower())
        cur = cur.value
    if isinstance(cur, ast.Name):
        tokens.append(cur.id.lower())
    tokens.reverse()
    return tokens


def _is_exempt_receiver(func: ast.Attribute) -> bool:
    """True if the receiver chain of a `.send_command` call mentions bridge/m4l."""
    tokens = _dotted_chain_tokens(func.value)
    return any(any(ex in tok for ex in EXEMPT_RECEIVER_TOKENS) for tok in tokens)


def _is_subprocess_call(func: ast.Attribute) -> bool:
    tokens = _dotted_chain_tokens(func)
    return "subprocess" in tokens[:-1]  # subprocess.<attr>(...)


def _classify_blocking_call(call: ast.Call) -> str | None:
    """Return a short label if `call` is one of the tracked blocking primitives."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None

    if func.attr == "send_command":
        if _is_exempt_receiver(func):
            return None
        return "send_command"

    if func.attr in FILE_IO_ATTRS:
        # Cheap false-positive guard: don't flag calls on obviously unrelated
        # receivers like io.BytesIO()/mock objects named `buf`/`stream` when
        # we can tell from the chain — but we keep this permissive since
        # pathlib.Path is the overwhelming real-world case and the whole
        # point of this scanner is to surface candidates for human review.
        return f"file_io:{func.attr}"

    if _is_subprocess_call(func):
        return f"subprocess:{func.attr}"

    return None


def _is_offload_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in OFFLOAD_ATTRS
    return False


@dataclass
class ParentIndex:
    parent: dict[int, ast.AST] = field(default_factory=dict)

    def link(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[id(child)] = node

    def ancestors(self, node: ast.AST):
        cur = self.parent.get(id(node))
        while cur is not None:
            yield cur
            cur = self.parent.get(id(cur))


def _is_wrapped(call: ast.Call, parents: ParentIndex, stop_at: ast.AST) -> bool:
    """True if `call` sits inside an ancestor to_thread/run_in_executor Call,
    without crossing out of `stop_at` (the enclosing function)."""
    for anc in parents.ancestors(call):
        if anc is stop_at:
            return False
        if _is_offload_call(anc):
            return True
        # Don't cross into a nested function definition's own scope boundary
        # accidentally — ast.walk/parent chain naturally stays within the
        # lexical tree so this is only a safety cap.
        if anc is None:
            break
    return False


def _collect_plain_helpers(module: ast.Module) -> dict[str, ast.FunctionDef]:
    """All same-file plain (sync) function/method defs, keyed by simple name.

    Best-effort: later definitions with the same simple name overwrite
    earlier ones (heuristic — this is a candidate-surfacing scanner, not a
    fully scoped resolver).
    """
    helpers: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef):
            helpers[node.name] = node
    return helpers


def _find_blocking_calls_in_body(
    func_node: ast.AST, parents: ParentIndex
) -> list[tuple[ast.Call, str]]:
    """Find unwrapped blocking calls anywhere in func_node's body (any depth,
    but does NOT descend into nested async def — those are scanned as their
    own top-level findings when ast.walk reaches them separately)."""
    found: list[tuple[ast.Call, str]] = []
    for node in ast.walk(func_node):
        if node is func_node:
            continue
        if isinstance(node, ast.Call):
            label = _classify_blocking_call(node)
            if label is None:
                continue
            if _is_wrapped(node, parents, func_node):
                continue
            found.append((node, label))
    return found


def _call_target_name(call: ast.Call) -> str | None:
    """Simple-name resolution for a call target: `helper(...)` or
    `self.helper(...)` / `obj.helper(...)` -> "helper"."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


# Repo root = the parent of scripts/. Used to keep baseline keys machine- and
# checkout-independent.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _repo_relative(file: str) -> str:
    """Best-effort repo-relative POSIX path for a scanned file."""
    try:
        return Path(file).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return Path(file).as_posix()


# ---------------------------------------------------------------------------
# Cross-file transitive detection
# ---------------------------------------------------------------------------


def _is_exempt_call(call: ast.Call) -> bool:
    """True if this call's receiver chain is one of the async-native exemptions.

    Reused for transitively-resolved calls. Without it, resolving the bare name
    `send_command` against the sync AbletonConnection definition would re-flag
    every `bridge.send_command(...)` site the direct rule deliberately exempts.
    """
    func = call.func
    return isinstance(func, ast.Attribute) and _is_exempt_receiver(func)


def _own_calls(func_node: ast.AST, parents: ParentIndex) -> list[ast.Call]:
    """Unwrapped calls made lexically BY func_node itself.

    Skips anything inside a nested `def`/`async def` (that body belongs to the
    nested function, not this one) and anything already inside a to_thread /
    run_in_executor wrapper.
    """
    out: list[ast.Call] = []
    for sub in ast.walk(func_node):
        if sub is func_node:
            continue
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(sub, ast.Call) and not _is_wrapped(sub, parents, func_node):
            out.append(sub)
    return out


@dataclass
class ProjectIndex:
    """Every function definition under the scan root, keyed by simple name."""

    by_name: dict[str, list[tuple[Path, ast.AST, bool]]] = field(default_factory=dict)
    parents: dict[Path, ParentIndex] = field(default_factory=dict)
    trees: dict[Path, ast.Module] = field(default_factory=dict)

    def sync_candidates(self, name: str, exclude: ast.AST | None) -> list[ast.AST]:
        """Sync definitions of `name`, minus `exclude` (the caller itself).

        Self-exclusion is what lets a thin wrapper that delegates to a
        same-named implementation elsewhere resolve at all — otherwise the
        name's candidate set contains the wrapper, which is not yet known to
        be blocking, and the "all candidates" rule deadlocks on itself.
        """
        return [
            node
            for (_p, node, is_async) in self.by_name.get(name, [])
            if not is_async and node is not exclude
        ]


def build_project_index(paths: list[Path]) -> ProjectIndex:
    index = ProjectIndex()
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue  # scan_file() already warns about these
        index.trees[path] = tree
        pi = ParentIndex()
        pi.link(tree)
        index.parents[path] = pi
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.by_name.setdefault(node.name, []).append(
                    (path, node, isinstance(node, ast.AsyncFunctionDef))
                )
    return index


def compute_blocking_functions(index: ProjectIndex) -> dict[int, tuple[str, str]]:
    """Fixed point over sync functions: id(node) -> (kind, detail).

    kind is "direct" (contains a tracked primitive) or "via" (calls something
    already known to be blocking). Terminates because the set only grows and
    is bounded by the number of definitions.
    """
    blocking: dict[int, tuple[str, str]] = {}
    all_sync = [
        (path, node)
        for defs in index.by_name.values()
        for (path, node, is_async) in defs
        if not is_async
    ]

    for path, node in all_sync:
        for call in _own_calls(node, index.parents[path]):
            label = _classify_blocking_call(call)
            if label:
                blocking[id(node)] = ("direct", label)
                break

    while True:
        changed = False
        for path, node in all_sync:
            if id(node) in blocking:
                continue
            for call in _own_calls(node, index.parents[path]):
                if _is_exempt_call(call):
                    continue
                name = _call_target_name(call)
                if not name:
                    continue
                candidates = index.sync_candidates(name, exclude=node)
                if candidates and all(id(c) in blocking for c in candidates):
                    blocking[id(node)] = ("via", name)
                    changed = True
                    break
        if not changed:
            return blocking


def _root_primitive(
    node: ast.AST, index: ProjectIndex, blocking: dict[int, tuple[str, str]], depth: int = 0
) -> str:
    """Walk the blocking chain down to the primitive that started it."""
    kind, detail = blocking[id(node)]
    if kind == "direct" or depth > 8:
        return detail
    nxt = [c for c in index.sync_candidates(detail, exclude=None) if id(c) in blocking]
    return _root_primitive(nxt[0], index, blocking, depth + 1) if nxt else detail


def scan_transitive(index: ProjectIndex) -> list[Violation]:
    """Async functions calling a transitively-blocking sync function."""
    blocking = compute_blocking_functions(index)
    violations: list[Violation] = []
    for path, tree in index.trees.items():
        parents = index.parents[path]
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for call in _own_calls(node, parents):
                # Already reported by the direct/one-hop rules, or exempt.
                if _classify_blocking_call(call) or _is_exempt_call(call):
                    continue
                name = _call_target_name(call)
                if not name:
                    continue
                candidates = index.sync_candidates(name, exclude=node)
                if not candidates or not all(id(c) in blocking for c in candidates):
                    continue
                target = candidates[0]
                violations.append(
                    Violation(
                        file=str(path),
                        lineno=call.lineno,
                        func_name=node.name,
                        kind="via_chain",
                        detail=_root_primitive(target, index, blocking),
                        helper_name=name,
                        helper_lineno=getattr(target, "lineno", None),
                    )
                )
    return violations


@dataclass
class Violation:
    file: str
    lineno: int
    func_name: str
    kind: str  # "direct", "via_helper", or "via_chain"
    detail: str
    helper_name: str | None = None
    helper_lineno: int | None = None

    def baseline_key(self) -> str:
        """Stable identity for baselining.

        Deliberately excludes lineno so an entry survives unrelated edits that
        shift the file, and normalises to a repo-relative POSIX path so the
        baseline matches on CI (a different checkout root) and on every other
        machine — an absolute key would miss everywhere but the box that
        generated it, turning the whole backlog back into "new" violations.
        """
        return f"{_repo_relative(self.file)}::{self.func_name}::{self.kind}::{self.helper_name or self.detail}"

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "lineno": self.lineno,
            "func_name": self.func_name,
            "kind": self.kind,
            "detail": self.detail,
            "helper_name": self.helper_name,
            "helper_lineno": self.helper_lineno,
        }


def scan_file(path: Path) -> list[Violation]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"WARN: could not read {path}: {exc}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        print(f"WARN: syntax error in {path}: {exc}", file=sys.stderr)
        return []

    parents = ParentIndex()
    parents.link(tree)

    plain_helpers = _collect_plain_helpers(tree)

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        # --- TYPE A: direct unwrapped blocking calls in this async fn ---
        direct_hits = _find_blocking_calls_in_body(node, parents)
        for call, label in direct_hits:
            violations.append(
                Violation(
                    file=str(path),
                    lineno=call.lineno,
                    func_name=node.name,
                    kind="direct",
                    detail=label,
                )
            )

        # --- TYPE B: one-level same-file hop through a plain-def helper ---
        for sub in ast.walk(node):
            if sub is node:
                continue
            if isinstance(sub, (ast.AsyncFunctionDef, ast.FunctionDef)) and sub is not node:
                # Don't treat calls made from a *nested* function definition
                # as if they were made directly by `node` — skip descending
                # into nested def bodies for the helper-hop check. (Nested
                # async defs get their own top-level scan pass anyway.)
                continue
            if not isinstance(sub, ast.Call):
                continue
            target_name = _call_target_name(sub)
            if target_name is None or target_name not in plain_helpers:
                continue
            helper_node = plain_helpers[target_name]
            if helper_node is node:
                continue
            if isinstance(helper_node, ast.AsyncFunctionDef):
                continue
            if _is_wrapped(sub, parents, node):
                continue
            helper_hits = _find_blocking_calls_in_body(helper_node, parents)
            for _call, label in helper_hits:
                violations.append(
                    Violation(
                        file=str(path),
                        lineno=sub.lineno,
                        func_name=node.name,
                        kind="via_helper",
                        detail=label,
                        helper_name=helper_node.name,
                        helper_lineno=helper_node.lineno,
                    )
                )

    return violations


def _scannable_paths(root: Path, exclude: set[str]) -> list[Path]:
    paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
    keep: list[Path] = []
    for path in paths:
        if "__pycache__" in path.parts:
            continue
        # Normalize to a mcp_server/... style relative path for exclude matching.
        try:
            rel_to_root_parent = path.relative_to(root.parent)
        except ValueError:
            rel_to_root_parent = path
        rel_str = str(rel_to_root_parent).replace("\\", "/")
        if rel_str in exclude:
            continue
        keep.append(path)
    return keep


def scan_tree(root: Path, exclude: set[str], transitive: bool = True) -> list[Violation]:
    """Per-file direct + one-hop scan, plus (by default) the project-wide
    transitive pass. `transitive=False` reproduces the pre-2026-07-31 behaviour."""
    paths = _scannable_paths(root, exclude)
    violations: list[Violation] = []
    for path in paths:
        violations.extend(scan_file(path))
    if transitive:
        violations.extend(scan_transitive(build_project_index(paths)))
    return violations


DEFAULT_BASELINE = Path(__file__).with_name("async_blocking_baseline.json")


def load_baseline(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return set(data.get("known_violations", []))


def split_baselined(
    violations: list[Violation], baseline: set[str]
) -> tuple[list[Violation], list[Violation]]:
    """-> (new, known). Anything not in the baseline is new and fails CI."""
    new: list[Violation] = []
    known: list[Violation] = []
    for v in violations:
        (known if v.baseline_key() in baseline else new).append(v)
    return new, known


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "root",
        nargs="?",
        default="mcp_server",
        help="Directory to scan recursively (default: mcp_server)",
    )
    ap.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="Relative file paths (e.g. mcp_server/server.py) to skip entirely",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    ap.add_argument(
        "--no-baseline",
        action="store_true",
        help="Report every violation, including the known pre-existing backlog",
    )
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite the baseline file from the current tree, then exit 0",
    )
    ap.add_argument(
        "--no-transitive",
        action="store_true",
        help="Direct + same-file one-hop only (pre-2026-07-31 behaviour)",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    exclude = set(args.exclude)

    violations = scan_tree(root, exclude, transitive=not args.no_transitive)

    if args.update_baseline:
        keys = sorted({v.baseline_key() for v in violations})
        # Group by root primitive so the backlog is a short work-list of root
        # causes rather than a long list of call sites. Most of the backlog
        # collapses onto a handful of blocking leaves — fixing one leaf clears
        # every site that reaches it.
        roots: dict[str, int] = {}
        for v in violations:
            roots[f"{v.helper_name or '?'}() -> {v.detail}"] = (
                roots.get(f"{v.helper_name or '?'}() -> {v.detail}", 0) + 1
            )
        DEFAULT_BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Known pre-existing 'blocking call on the event loop' sites, "
                        "recorded so CI fails on NEW violations instead of the backlog. "
                        "Keyed by (repo-relative file, function, kind, target) — not line "
                        "number, and not an absolute path, so the baseline matches on CI "
                        "and on every developer machine. Shrinking this list is the goal; "
                        "adding to it needs a reason. Regenerate with: "
                        "python3 scripts/scan_async_blocking.py --update-baseline"
                    ),
                    "_root_causes": dict(
                        sorted(roots.items(), key=lambda kv: (-kv[1], kv[0]))
                    ),
                    "known_violations": keys,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Baseline updated: {len(keys)} known violation(s) -> {DEFAULT_BASELINE}")
        return 0

    known: list[Violation] = []
    if not args.no_baseline:
        violations, known = split_baselined(violations, load_baseline(DEFAULT_BASELINE))

    if args.json:
        print(json.dumps([v.to_dict() for v in violations], indent=2))
    else:
        if not violations:
            print("No violations found.")
            if known:
                print(
                    f"({len(known)} known pre-existing site(s) suppressed by "
                    f"{DEFAULT_BASELINE.name} — run with --no-baseline to see them.)"
                )
        else:
            by_file: dict[str, list[Violation]] = {}
            for v in violations:
                by_file.setdefault(v.file, []).append(v)
            for file, vs in by_file.items():
                print(f"\n{file}  ({len(vs)} violation(s))")
                for v in vs:
                    if v.kind == "direct":
                        print(f"  L{v.lineno}: async def {v.func_name}() -> direct unwrapped {v.detail}")
                    elif v.kind == "via_chain":
                        print(
                            f"  L{v.lineno}: async def {v.func_name}() -> calls {v.helper_name}() "
                            f"(L{v.helper_lineno}) which transitively reaches {v.detail}"
                        )
                    else:
                        print(
                            f"  L{v.lineno}: async def {v.func_name}() -> calls helper "
                            f"{v.helper_name}() (L{v.helper_lineno}) which has unwrapped {v.detail}"
                        )
            print(f"\nTotal: {len(violations)} violation(s) across {len(by_file)} file(s).")
            if known:
                print(f"({len(known)} additional known site(s) suppressed by {DEFAULT_BASELINE.name}.)")

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
