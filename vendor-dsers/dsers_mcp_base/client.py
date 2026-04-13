"""Authenticated HTTP client for DSers BFF APIs — auto-retries on expired tokens."""

from __future__ import annotations

import asyncio
import json as _json
import time
from typing import Any, Optional

import httpx

from dsers_mcp_base.auth import DSersAuth
from dsers_mcp_base.config import DSersConfig

# ── Rate limiter ────────────────────────────────────────────────
_rate_timestamps: list[float] = []
_RATE_LIMIT_WINDOW = 1.0
_RATE_LIMIT_MAX = 20


async def _throttle():
    now = time.monotonic()
    _rate_timestamps[:] = [t for t in _rate_timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_timestamps) >= _RATE_LIMIT_MAX:
        wait = _RATE_LIMIT_WINDOW - (now - _rate_timestamps[0]) + 0.05
        if wait > 0:
            await asyncio.sleep(wait)
    _rate_timestamps.append(time.monotonic())


RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class DSersClient:
    def __init__(self, config: DSersConfig) -> None:
        self._config = config
        self._auth = DSersAuth(config)
        self._http: Optional[httpx.AsyncClient] = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=60)
        return self._http

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        _retried: bool = False,
    ) -> dict:
        await _throttle()

        session_id, state = await self._auth.get_session()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session_id}",
        }
        cookies = {"session_id": session_id, "state": state}

        http = self._get_http()
        resp = await http.request(
            method,
            f"{self._config.base_url}{path}",
            headers=headers,
            cookies=cookies,
            params=_strip_none(params),
            json=json,
        )

        # auto-retry once on token expiry
        if resp.status_code in (400, 401) and not _retried:
            body = resp.json()
            if body.get("reason") in ("TOKEN_NOT_FOUND", "TOKEN_EXPIRED", "UNAUTHORIZED", "INVALID_TOKEN"):
                self._auth.invalidate()
                return await self.request(method, path, params=params, json=json, _retried=True)

        # retry on transient server errors
        if resp.status_code in RETRYABLE_STATUS and not _retried:
            retry_after = float(resp.headers.get("retry-after", "2"))
            await asyncio.sleep(min(retry_after, 30))
            return await self.request(method, path, params=params, json=json, _retried=True)

        if resp.status_code >= 400:
            raise DSersAPIError(resp.status_code, resp.text)

        return resp.json()

    async def get(self, path: str, **params: Any) -> dict:
        return await self.request("GET", path, params=params or None)

    async def post(self, path: str, json: Optional[dict] = None, **params: Any) -> dict:
        return await self.request("POST", path, json=json, params=params or None)

    async def put(self, path: str, json: Optional[dict] = None, **params: Any) -> dict:
        return await self.request("PUT", path, json=json, params=params or None)

    async def delete(self, path: str, **params: Any) -> dict:
        return await self.request("DELETE", path, params=params or None)

    async def login(self) -> dict:
        sid, state = await self._auth.login()
        return {"session_id": sid, "state": state}


class DSersAPIError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"DSers API {status}: {body[:500]}")


def _strip_none(d: Optional[dict]) -> Optional[dict]:
    if d is None:
        return None
    return {k: v for k, v in d.items() if v is not None}
