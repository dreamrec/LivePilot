"""Regression guard for the scanner's cross-file transitive detection.

Context: the 2026-07-31 deep review found a real "blocking call on the event
loop" defect that `scripts/scan_async_blocking.py` did NOT catch —
`commit_preview_variant` (async, mcp_server/preview_studio/tools.py) called
`record_turn_resolution()` (mcp_server/session_continuity/tracker.py), which
holds a `threading.Lock` while calling `_project_store.save_turn()` -> ... ->
`base_store.write()`, whose `mkdir`/`open`/`os.fsync` are the actual blocking
primitives. Three hops across three files; the scanner's helper index was
same-file and one-hop only, so nothing fired.

The tests below pin both halves of the fix:
  * the scanner now flags that shape (`test_scanner_flags_*`), and
  * the real call site is fixed and stays fixed (`test_real_*`).

The synthetic fixtures deliberately mirror the real chain's SHAPE (async ->
cross-file sync fn -> lock-holding sync fn -> file-I/O primitive) rather than
importing the real modules, so the test keeps proving the detection mechanism
even after the production code is refactored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.scan_async_blocking import (  # noqa: E402
    DEFAULT_BASELINE,
    build_project_index,
    load_baseline,
    scan_file,
    scan_transitive,
    scan_tree,
)

# --- fixture sources: the pre-fix commit_preview_variant chain, minimised ----

_STORE_PY = '''
from pathlib import Path

class ProjectStore:
    def __init__(self, path):
        self._path = Path(path)

    def write(self, data):
        """The leaf primitive — mirrors persistence/base_store.py::write."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(data, encoding="utf-8")

    def save_turn(self, turn):
        self.write(str(turn))
'''

_TRACKER_PY = '''
import threading

_state_lock = threading.Lock()
_project_store = None

def record_turn_resolution(request_text, outcome="accepted"):
    """Mirrors session_continuity/tracker.py — holds a lock across disk I/O."""
    with _state_lock:
        if _project_store is not None:
            _project_store.save_turn({"request": request_text, "outcome": outcome})
    return True

def resolve_thread(thread_id):
    with _state_lock:
        if _project_store is not None:
            _project_store.save_turn({"thread": thread_id})
    return thread_id
'''

# The defect: async handler calls the cross-file sync function bare.
_TOOLS_PRE_FIX_PY = '''
from tracker import record_turn_resolution, resolve_thread

async def commit_preview_variant(ctx, variant_id):
    record_turn_resolution(request_text="preview", outcome="accepted")
    resolve_thread(variant_id)
    return {"ok": True}
'''

# The fix that actually shipped in commit 75a6ea4.
_TOOLS_FIXED_PY = '''
import asyncio

from tracker import record_turn_resolution, resolve_thread

async def commit_preview_variant(ctx, variant_id):
    await asyncio.to_thread(
        record_turn_resolution, request_text="preview", outcome="accepted"
    )
    await asyncio.to_thread(resolve_thread, variant_id)
    return {"ok": True}
'''


def _write_pkg(tmp_path: Path, tools_src: str) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "store.py").write_text(_STORE_PY, encoding="utf-8")
    (pkg / "tracker.py").write_text(_TRACKER_PY, encoding="utf-8")
    (pkg / "tools.py").write_text(tools_src, encoding="utf-8")
    return pkg


def _transitive(pkg: Path):
    return scan_transitive(build_project_index(sorted(pkg.rglob("*.py"))))


# --- the headline regression -------------------------------------------------


def test_scanner_flags_pre_fix_commit_preview_variant_shape(tmp_path):
    """THE regression: the exact shape the old scanner missed must now fail.

    async commit_preview_variant -> record_turn_resolution (other file)
      -> ProjectStore.save_turn (other file) -> write() -> mkdir/write_text
    """
    pkg = _write_pkg(tmp_path, _TOOLS_PRE_FIX_PY)

    # First prove this test is not a tautology: the PRE-widening rule (per-file
    # scan_file, direct + same-file one hop) must miss this entirely. If this
    # ever starts finding the chain, the test below stops proving anything.
    old_rule = [v for p in sorted(pkg.rglob("*.py")) for v in scan_file(p)]
    assert not old_rule, (
        "the pre-widening rule was expected to MISS this chain; if it now "
        f"catches it, this regression test no longer proves the fix: {old_rule}"
    )

    violations = _transitive(pkg)

    offenders = [v for v in violations if v.func_name == "commit_preview_variant"]
    assert offenders, (
        "scanner failed to flag the cross-file transitive blocking chain that "
        "the 2026-07-31 review found — this is the exact defect the widened "
        f"rule exists to catch. Got: {[v.to_dict() for v in violations]}"
    )
    targets = {v.helper_name for v in offenders}
    assert targets == {"record_turn_resolution", "resolve_thread"}, targets
    assert all(v.kind == "via_chain" for v in offenders)
    # The reported root must be the real primitive, not the intermediate hop.
    assert all("file_io" in v.detail for v in offenders), [v.detail for v in offenders]


def test_scanner_accepts_the_offloaded_fix(tmp_path):
    """The shipped fix (asyncio.to_thread) must clear the violation — otherwise
    the guard would be unsatisfiable and teams would just disable it."""
    violations = _transitive(_write_pkg(tmp_path, _TOOLS_FIXED_PY))
    assert not [v for v in violations if v.func_name == "commit_preview_variant"], (
        f"to_thread-wrapped calls must not be flagged: {[v.to_dict() for v in violations]}"
    )


# --- false-positive controls -------------------------------------------------


def test_ambiguous_name_does_not_propagate_when_a_candidate_is_clean(tmp_path):
    """Simple-name resolution is ambiguous (149 of 1757 names in mcp_server/ are
    defined more than once). A caller is only marked blocking when EVERY
    candidate definition of that name blocks — otherwise `to_dict()` (157
    definitions) and friends would poison the whole tree."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text(
        'from pathlib import Path\n'
        'def persist(p):\n'
        '    Path(p).write_text("x", encoding="utf-8")\n',
        encoding="utf-8",
    )
    (pkg / "b.py").write_text('def persist(p):\n    return {"cached": p}\n', encoding="utf-8")
    (pkg / "c.py").write_text('async def handler(p):\n    return persist(p)\n', encoding="utf-8")

    violations = _transitive(pkg)
    assert not violations, (
        "an ambiguous name with at least one non-blocking definition must not "
        f"propagate: {[v.to_dict() for v in violations]}"
    )


def test_exempt_bridge_receiver_is_not_flagged_transitively(tmp_path):
    """The bridge/m4l/spectral receivers are async-native and must never be
    wrapped in to_thread. Resolving `send_command` by bare NAME would otherwise
    re-flag every already-exempt `bridge.send_command(...)` site — which is
    exactly what happened on the first draft of this rule (76 hits, 34 bogus)."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "conn.py").write_text(
        'from pathlib import Path\n'
        'class Conn:\n'
        '    def send_command(self, name):\n'
        '        Path("/tmp/x").write_text(name, encoding="utf-8")\n',
        encoding="utf-8",
    )
    (pkg / "use.py").write_text(
        'async def reads_bridge(bridge):\n    return bridge.send_command("ping")\n',
        encoding="utf-8",
    )
    violations = _transitive(pkg)
    assert not violations, (
        f"bridge receivers must stay exempt transitively: {[v.to_dict() for v in violations]}"
    )


def test_lambda_bodies_are_not_treated_as_inline_code(tmp_path):
    """A lambda body is a DEFERRED execution context.

    `agent_os.py` builds `capture_fn = lambda: _capture_snapshot(ctx)` and hands
    it to `experiment/engine.py`, which invokes it via
    `await asyncio.to_thread(capture_fn)`. The work is already offloaded — at
    the consumer, not the definition site. Treating the lambda body as inline
    code of the defining function reported 4 already-correct calls as
    violations, which is exactly how a lint loses its credibility.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "prim.py").write_text(
        'from pathlib import Path\n'
        'def snapshot(ctx):\n'
        '    Path("/tmp/s").write_text(str(ctx), encoding="utf-8")\n',
        encoding="utf-8",
    )
    (pkg / "use.py").write_text(
        'async def handler(ctx):\n'
        '    capture_fn = lambda: snapshot(ctx)\n'   # deferred — not a call here
        '    return await run_it(capture_fn)\n'
        'async def run_it(fn):\n'
        '    import asyncio\n'
        '    return await asyncio.to_thread(fn)\n',
        encoding="utf-8",
    )
    violations = _transitive(pkg)
    assert not violations, (
        "a call inside a lambda body must not be attributed to the defining "
        f"function: {[v.to_dict() for v in violations]}"
    )


def test_nested_function_calls_are_not_double_reported(tmp_path):
    """`ast.walk` is breadth-first over ALL descendants, so `continue` on a
    nested def does not stop it yielding that def's children. The original
    walk claimed (in its docstring) not to descend but actually did, so a
    blocking call inside a nested `async def` was reported twice — once for
    the nested function, once for its parent.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "prim.py").write_text(
        'from pathlib import Path\n'
        'def persist(x):\n'
        '    Path("/tmp/p").write_text(str(x), encoding="utf-8")\n',
        encoding="utf-8",
    )
    (pkg / "use.py").write_text(
        'async def outer(x):\n'
        '    async def inner(y):\n'
        '        return persist(y)\n'
        '    return await inner(x)\n',
        encoding="utf-8",
    )
    violations = _transitive(pkg)
    assert len(violations) == 1, (
        "the blocking call belongs to `inner` only — reporting it for `outer` "
        f"too is double-counting: {[v.to_dict() for v in violations]}"
    )
    assert violations[0].func_name == "inner", violations[0].to_dict()


def test_self_referential_wrapper_resolves_instead_of_deadlocking(tmp_path):
    """A thin wrapper delegating to a same-named implementation in another
    module (session_continuity/tools.py -> tracker.py::record_turn_resolution)
    must still resolve. Without excluding a function from its own candidate
    set, the "all candidates" rule can never conclude anything about it."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "impl.py").write_text(
        'from pathlib import Path\n'
        'def do_work(x):\n'
        '    Path("/tmp/w").write_text(str(x), encoding="utf-8")\n',
        encoding="utf-8",
    )
    (pkg / "wrapper.py").write_text(
        'import impl\ndef do_work(x):\n    return impl.do_work(x)\n', encoding="utf-8"
    )
    (pkg / "caller.py").write_text('async def handler(x):\n    return do_work(x)\n', encoding="utf-8")

    violations = _transitive(pkg)
    assert [v.func_name for v in violations] == ["handler"], (
        "the wrapper chain must resolve through the self-name collision: "
        f"{[v.to_dict() for v in violations]}"
    )


# --- the real tree -----------------------------------------------------------


def test_real_commit_preview_variant_is_not_flagged():
    """The production fix from commit 75a6ea4 must hold."""
    tools = REPO_ROOT / "mcp_server" / "preview_studio" / "tools.py"
    tracker = REPO_ROOT / "mcp_server" / "session_continuity" / "tracker.py"
    violations = scan_transitive(build_project_index([tools, tracker]))
    assert not [v for v in violations if v.func_name == "commit_preview_variant"], (
        "commit_preview_variant regressed to blocking the event loop: "
        f"{[v.to_dict() for v in violations]}"
    )


def test_real_commit_preview_variant_is_not_hidden_by_the_baseline():
    """A baseline that suppressed the very defect it was introduced alongside
    would be worse than no baseline at all."""
    assert not [k for k in load_baseline(DEFAULT_BASELINE) if "commit_preview_variant" in k]


def test_no_new_blocking_violations_tree_wide():
    """CI gate: the baseline covers the known backlog, so anything else is new.

    If this fails, either offload the new call (asyncio.to_thread /
    run_in_executor / send_command_async) or, with a stated reason, regenerate
    the baseline via `python3 scripts/scan_async_blocking.py --update-baseline`.
    """
    mcp_server = REPO_ROOT / "mcp_server"
    if not mcp_server.is_dir():  # pragma: no cover
        pytest.skip("mcp_server/ not present")
    violations = scan_tree(mcp_server, exclude={"mcp_server/splice_client/protos"})
    baseline = load_baseline(DEFAULT_BASELINE)
    new = [v for v in violations if v.baseline_key() not in baseline]
    assert not new, (
        "new blocking-call-on-the-event-loop site(s) introduced:\n"
        + "\n".join(
            f"  {v.file}:{v.lineno} async def {v.func_name}() -> "
            f"{v.helper_name or v.detail} ({v.detail})"
            for v in new
        )
    )


def test_baseline_file_is_well_formed_and_shrinking_is_possible():
    """The baseline must stay machine-checkable — a hand-edited blob that no
    longer round-trips would silently stop suppressing (or start hiding) sites."""
    data = json.loads(DEFAULT_BASELINE.read_text(encoding="utf-8"))
    keys = data["known_violations"]
    assert keys == sorted(set(keys)), "baseline must be sorted and de-duplicated"
    assert all(k.count("::") == 3 for k in keys), "unexpected baseline key shape"


def test_baseline_is_empty():
    """The backlog was driven to zero on 2026-07-31 (42 -> 0: 6 were scanner
    false positives, 36 were real and fixed).

    Keeping it at zero is the point. If this fails, someone baselined a new
    blocking call instead of offloading it — `asyncio.to_thread`,
    `run_in_executor`, or `send_command_async` is almost always the right
    answer. Deliberately re-baselining is a decision worth recording here with
    a reason, not a silent `--update-baseline`.
    """
    keys = load_baseline(DEFAULT_BASELINE)
    assert not keys, (
        "the async-blocking baseline is no longer empty — these sites block "
        f"the event loop and should be offloaded rather than suppressed:\n"
        + "\n".join(f"  {k}" for k in sorted(keys))
    )
