"""Root conftest — adds repo root to sys.path so `mcp_server` resolves in CI.

Locally, dev installs (`pip install -e .` etc.) put `mcp_server` on path. In
CI the workflow runs raw `pytest tests/ -v` without an editable install, and
because `tests/composer/*/__init__.py` makes those dirs packages, pytest
doesn't auto-insert the rootdir. Result: `ModuleNotFoundError: mcp_server`
on every test in `tests/composer/`.

Adding the repo root here makes both paths work without touching CI yaml or
deleting the package __init__.py files.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
