"""
Structured JSON logger — outputs to stderr to keep stdout clean for MCP protocol frames.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

VALID_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
DEFAULT_LEVEL = "info"

_cached_level: Optional[str] = None


def _current_level() -> str:
    global _cached_level
    if _cached_level is not None:
        return _cached_level
    raw = os.environ.get("LOG_LEVEL", "").lower()
    _cached_level = raw if raw in VALID_LEVELS else DEFAULT_LEVEL
    return _cached_level


def _emit(level: str, msg: str, ctx: Optional[dict[str, Any]] = None) -> None:
    if VALID_LEVELS.get(level, 0) < VALID_LEVELS.get(_current_level(), 20):
        return
    record: dict[str, Any] = {
        "time": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
    }
    if ctx:
        try:
            json.dumps(ctx)
            record["ctx"] = ctx
        except (TypeError, ValueError):
            record["ctx"] = {"_stringify_failed": True}
    try:
        sys.stderr.write(json.dumps(record) + "\n")
    except Exception:
        pass


class _Logger:
    @staticmethod
    def debug(msg: str, ctx: Optional[dict[str, Any]] = None) -> None:
        _emit("debug", msg, ctx)

    @staticmethod
    def info(msg: str, ctx: Optional[dict[str, Any]] = None) -> None:
        _emit("info", msg, ctx)

    @staticmethod
    def warn(msg: str, ctx: Optional[dict[str, Any]] = None) -> None:
        _emit("warn", msg, ctx)

    @staticmethod
    def error(msg: str, ctx: Optional[dict[str, Any]] = None) -> None:
        _emit("error", msg, ctx)


log = _Logger()
