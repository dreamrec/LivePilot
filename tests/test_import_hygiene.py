"""Import-hygiene regression tests.

Catches the "logger used before defined" class of bug. A previous release
had three files where logger.debug was called from a function whose logger
binding lived later in the file (or, in one case, inside a docstring). The
bug was latent because the exception path was rarely hit — but when it did
fire, it raised NameError instead of logging the original exception.

This test walks every .py file in mcp_server/ and asserts that any file
which calls logger.<method> has a module-top logger definition BEFORE the
first call.
"""
from __future__ import annotations

import pathlib
import re

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "mcp_server"

USAGE_RE = re.compile(r"(?<![a-zA-Z_])logger\.(debug|info|warning|error|exception|critical)")
DEF_RE = re.compile(r"^\s*logger\s*=\s*logging\.getLogger")


def _strip_strings_and_comments(src: str) -> str:
    """Remove triple-quoted strings and # comments so logger. matches inside
    docstrings are not counted as real usages. Naive but sufficient for a
    static lint — we only need to avoid docstring false positives."""
    # Remove triple-quoted strings
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    # Remove comment-only lines (the real regex tolerates them, but be safe)
    lines = [re.sub(r"#.*$", "", ln) for ln in src.splitlines()]
    return "\n".join(lines)


def _python_files():
    for p in TARGET_DIR.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


@pytest.mark.parametrize("path", list(_python_files()), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_logger_defined_before_use(path):
    """Every mcp_server module that uses logger.X must define logger at
    module top before the first use."""
    src = path.read_text()
    cleaned = _strip_strings_and_comments(src)

    use_lines = [i for i, line in enumerate(cleaned.splitlines(), 1)
                 if USAGE_RE.search(line)]
    def_lines = [i for i, line in enumerate(cleaned.splitlines(), 1)
                 if DEF_RE.match(line)]

    if not use_lines:
        return  # nothing to check

    first_use = min(use_lines)
    if not def_lines:
        pytest.fail(
            f"{path.relative_to(REPO_ROOT)}: uses logger.X at line {first_use} "
            f"but has no 'logger = logging.getLogger(...)' definition."
        )
    first_def = min(def_lines)
    assert first_def < first_use, (
        f"{path.relative_to(REPO_ROOT)}: logger used at line {first_use} "
        f"before its definition at line {first_def}. "
        f"Move 'logger = logging.getLogger(__name__)' to the top of the file."
    )
