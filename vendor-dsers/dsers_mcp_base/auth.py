"""DSers authentication — login, session caching, and auto-refresh."""

from __future__ import annotations

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows
import json
import time
from pathlib import Path
from typing import Optional

import httpx

from dsers_mcp_base.config import DSersConfig

_SESSION_TTL = 3600 * 6  # treat session as stale after 6 hours


class DSersAuth:
    def __init__(self, config: DSersConfig) -> None:
        self._config = config
        self._session_id: Optional[str] = None
        self._state: Optional[str] = None
        self._fetched_at: float = 0

    async def get_session(self) -> tuple[str, str]:
        if self._session_id and (time.time() - self._fetched_at < _SESSION_TTL):
            return self._session_id, self._state or ""

        cached = self._read_cache()
        if cached:
            self._session_id, self._state, self._fetched_at = cached
            return self._session_id, self._state

        return await self.login()

    async def login(self) -> tuple[str, str]:
        if not self._config.email or not self._config.password:
            raise ValueError("DSERS_EMAIL and DSERS_PASSWORD are required")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._config.base_url}/account-user-bff/v1/users/login",
                json={"email": self._config.email, "password": self._config.password},
            )
            resp.raise_for_status()
            data = resp.json()

        inner = data.get("data")
        if not inner or "sessionId" not in inner:
            raise RuntimeError(f"Login failed: {data}")

        self._session_id = inner["sessionId"]
        self._state = inner.get("state", "")
        self._fetched_at = time.time()
        self._write_cache()
        return self._session_id, self._state

    def invalidate(self) -> None:
        self._session_id = None
        self._state = None
        self._fetched_at = 0

    # ── file-based session cache (shared across modules) ─────────────

    def _read_cache(self) -> Optional[tuple[str, str, float]]:
        p = self._config.session_file
        if not p.exists():
            return None
        try:
            with p.open("r") as fh:
                if fcntl:
                    fcntl.flock(fh, fcntl.LOCK_SH)
                obj = json.load(fh)
                if fcntl:
                    fcntl.flock(fh, fcntl.LOCK_UN)
            ts = obj.get("ts", 0)
            if time.time() - ts > _SESSION_TTL:
                return None
            return obj["session_id"], obj.get("state", ""), ts
        except Exception:
            return None  # intentionally suppressed — corrupt or unreadable cache is treated as absent

    def _write_cache(self) -> None:
        p = self._config.session_file
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "session_id": self._session_id,
            "state": self._state,
            "ts": self._fetched_at,
        })
        with p.open("w") as fh:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(payload)
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_UN)
