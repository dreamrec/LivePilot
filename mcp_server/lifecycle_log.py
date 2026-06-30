"""Best-effort lifecycle logging for LivePilot process exits."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Optional


_DEFAULT_LOG_PATH = Path.home() / ".livepilot" / "logs" / "lifecycle.jsonl"


def lifecycle_log_path() -> Optional[Path]:
    value = os.environ.get("LIVEPILOT_LIFECYCLE_LOG")
    if value and value.lower() in {"0", "false", "off", "no"}:
        return None
    return Path(value).expanduser() if value else _DEFAULT_LOG_PATH


def lifecycle_event(event: str, **fields) -> None:
    """Append one JSONL lifecycle event without ever breaking runtime code."""
    path = lifecycle_log_path()
    if path is None:
        return
    record = {
        "ts_ms": int(time.time() * 1000),
        "event": event,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "argv": list(sys.argv),
        "cwd": os.getcwd(),
    }
    record.update(fields)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str, sort_keys=True))
            handle.write("\n")
    except Exception:
        pass


def exception_fields(exc: BaseException) -> dict:
    return {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-12000:],
    }
