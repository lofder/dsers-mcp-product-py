"""Authenticated HTTP client for DSers BFF APIs — auto-retries on expired tokens."""

from __future__ import annotations

import json as _json
from typing import Any, Optional

import httpx

from dsers_mcp_base.auth import DSersAuth
from dsers_mcp_base.config import DSersConfig


class DSersClient:
    def __init__(self, config: DSersConfig) -> None:
        self._config = config
        self._auth = DSersAuth(config)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        _retried: bool = False,
    ) -> dict:
        session_id, state = await self._auth.get_session()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session_id}",
        }
        cookies = {"session_id": session_id, "state": state}

        async with httpx.AsyncClient(timeout=60) as http:
            resp = await http.request(
                method,
                f"{self._config.base_url}{path}",
                headers=headers,
                cookies=cookies,
                params=_strip_none(params),
                json=json,
            )

        # auto-retry once on token expiry
        if resp.status_code == 400 and not _retried:
            body = resp.json()
            if body.get("reason") in ("TOKEN_NOT_FOUND", "TOKEN_EXPIRED", "UNAUTHORIZED", "INVALID_TOKEN"):
                self._auth.invalidate()
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
