"""
Smithery entry point — wraps the existing server logic for Smithery distribution.

This module is referenced by pyproject.toml [tool.smithery] and provides
the create_server factory that Smithery calls to spin up the MCP server.
Credentials are passed via Smithery's session config (CLI args in local mode)
and bridged into env vars so the existing provider chain works unchanged.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
from smithery import Server


class DsersConfig(BaseModel):
    dsers_email: str = Field(description="DSers account email")
    dsers_password: str = Field(description="DSers account password")
    dsers_env: str = Field(default="production", description="Environment: production or test")


@Server("dsers-mcp-product", config_schema=DsersConfig)
def create_server():
    pass


# ---------------------------------------------------------------------------
#  Lazy service initialisation
# ---------------------------------------------------------------------------

_service = None
STATE_DIR = Path(
    os.getenv("IMPORT_MCP_STATE_DIR", str(Path(__file__).resolve().parent.parent / ".state"))
)


def _get_service():
    global _service
    if _service is None:
        ctx = create_server.get_context()
        cfg = ctx.session_config
        os.environ["DSERS_EMAIL"] = cfg.dsers_email
        os.environ["DSERS_PASSWORD"] = cfg.dsers_password
        os.environ["DSERS_ENV"] = cfg.dsers_env

        from dsers_mcp_product.job_store import FileJobStore
        from dsers_mcp_product.provider import load_provider
        from dsers_mcp_product.service import ImportFlowService

        _service = ImportFlowService(load_provider(), FileJobStore(STATE_DIR))
    return _service


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
#  Tool definitions — thin wrappers around ImportFlowService methods
# ---------------------------------------------------------------------------


@create_server.tool()
async def get_rule_capabilities(target_store: str = "") -> str:
    """Show supported rule families, stores, visibility modes, and push options for the currently loaded provider."""
    result = await _get_service().get_rule_capabilities(
        {"target_store": target_store or None}
    )
    return _to_json(result)


@create_server.tool()
async def validate_rules(rules: dict, target_store: str = "") -> str:
    """Validate and normalize a structured rule object against the currently loaded provider before preparing an import candidate."""
    result = await _get_service().validate_rules(
        {"rules": rules, "target_store": target_store or None}
    )
    return _to_json(result)


@create_server.tool()
async def prepare_import_candidate(
    source_url: str = "",
    source_urls: Optional[list] = None,
    source_hint: str = "auto",
    country: str = "US",
    target_store: str = "",
    visibility_mode: str = "backend_only",
    rules: Optional[dict] = None,
) -> str:
    """Import products from supplier URLs and return preview bundles.

    Single mode: provide source_url.
    Batch mode: provide source_urls (list of URL strings or {url, rules?, ...} objects).
    """
    payload: dict = {}
    if source_urls:
        payload["source_urls"] = source_urls
    elif source_url:
        payload["source_url"] = source_url
    if source_hint:
        payload["source_hint"] = source_hint
    if country:
        payload["country"] = country
    if target_store:
        payload["target_store"] = target_store
    if visibility_mode:
        payload["visibility_mode"] = visibility_mode
    if rules:
        payload["rules"] = rules
    result = await _get_service().prepare_import_candidate(payload)
    return _to_json(result)


@create_server.tool()
async def get_import_preview(job_id: str) -> str:
    """Load a previously prepared preview bundle by job_id."""
    result = await _get_service().get_import_preview({"job_id": job_id})
    return _to_json(result)


@create_server.tool()
async def set_product_visibility(job_id: str, visibility_mode: str) -> str:
    """Update the requested visibility mode (backend_only or sell_immediately) for a prepared job before confirmation."""
    result = await _get_service().set_product_visibility(
        {"job_id": job_id, "visibility_mode": visibility_mode}
    )
    return _to_json(result)


@create_server.tool()
async def confirm_push_to_store(
    job_id: str = "",
    job_ids: Optional[list] = None,
    target_store: str = "",
    target_stores: Optional[list] = None,
    visibility_mode: str = "",
    push_options: Optional[dict] = None,
) -> str:
    """Push prepared drafts to store(s).

    Single: job_id + target_store.
    Batch: job_ids list (each can be a string or {job_id, target_store?, ...} object).
    Multi-store: target_stores list — one job pushed to N stores.
    """
    payload: dict = {}
    if job_ids:
        payload["job_ids"] = job_ids
    elif job_id:
        payload["job_id"] = job_id
    if target_store:
        payload["target_store"] = target_store
    if target_stores:
        payload["target_stores"] = target_stores
    if visibility_mode:
        payload["visibility_mode"] = visibility_mode
    if push_options:
        payload["push_options"] = push_options
    result = await _get_service().confirm_push_to_store(payload)
    return _to_json(result)


@create_server.tool()
async def get_job_status(job_id: str) -> str:
    """Get the current status for a prepared or pushed job."""
    result = await _get_service().get_job_status({"job_id": job_id})
    return _to_json(result)
