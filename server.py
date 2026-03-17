#!/usr/bin/env python3
"""
Dropship Import MCP Server — Entry point for the product import workflow.
代发货导入 MCP 服务器 —— 商品导入工作流的入口点

Registers seven MCP tools covering single, batch, and multi-store workflows:
  1. get_rule_capabilities    — discover provider features
  2. validate_rules           — dry-run rule validation
  3. prepare_import_candidate — import single URL or batch of URLs
  4. get_import_preview       — reload a saved preview
  5. set_product_visibility   — toggle draft / live
  6. confirm_push_to_store    — push single/batch/multi-store
  7. get_job_status            — poll job state

注册七个 MCP 工具，覆盖单条、批量和多店铺工作流：
  1. get_rule_capabilities    — 发现提供者功能
  2. validate_rules           — 规则校验试运行
  3. prepare_import_candidate — 导入单条或批量 URL
  4. get_import_preview       — 重新加载已保存的预览
  5. set_product_visibility   — 切换草稿 / 上架
  6. confirm_push_to_store    — 单条/批量/多店铺推送
  7. get_job_status            — 查询任务状态
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from dropship_import_mcp.job_store import FileJobStore
from dropship_import_mcp.provider import load_provider
from dropship_import_mcp.service import ImportFlowService

load_dotenv()

# Job state directory — each import job is persisted as a JSON file here.
# 任务状态目录 —— 每个导入任务以 JSON 文件形式持久化在此目录。
STATE_DIR = Path(os.getenv("IMPORT_MCP_STATE_DIR", Path(__file__).resolve().parent / ".state"))

# Provider and service are instantiated once at startup.
# 提供者和服务在启动时实例化一次。
PROVIDER = load_provider()
SERVICE = ImportFlowService(PROVIDER, FileJobStore(STATE_DIR))

app = Server("public-dropship-import-mcp")


def _reply_json(data: Any) -> list[TextContent]:
    """Wrap any data as a JSON TextContent response. / 将任何数据包装为 JSON TextContent 响应。"""
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


# ──────────────────────────────────────────────────────────────
#  Tool definitions / 工具定义
# ──────────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="get_rule_capabilities",
        description="Show supported rule families, stores, visibility modes, and push options for the currently loaded provider.",
        inputSchema={
            "type": "object",
            "properties": {
                "target_store": {"type": "string", "description": "Optional store ref or display name to inspect"},
            },
            "required": [],
        },
    ),
    Tool(
        name="validate_rules",
        description="Validate and normalize a structured rule object against the currently loaded provider before preparing an import candidate.",
        inputSchema={
            "type": "object",
            "properties": {
                "target_store": {"type": "string", "description": "Optional store ref or display name to validate against"},
                "rules": {
                    "type": "object",
                    "description": "Structured rule object with pricing, content, images, and optional instruction_text.",
                },
            },
            "required": ["rules"],
        },
    ),
    Tool(
        name="prepare_import_candidate",
        description=(
            "Import products from supplier URLs and return preview bundles. "
            "Supports single mode (source_url) and batch mode (source_urls). "
            "In batch mode, each URL is processed independently — failures do not block other items."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "source_url": {"type": "string", "description": "Single source product URL (single mode)"},
                "source_urls": {
                    "type": "array",
                    "description": (
                        "Batch mode: list of URLs to import. Each item can be a plain URL string "
                        "or an object {url, source_hint?, country?, target_store?, rules?} for per-item overrides. "
                        "When present, source_url is ignored."
                    ),
                    "items": {},
                },
                "source_hint": {"type": "string", "description": "Optional source hint: auto, aliexpress, accio"},
                "country": {"type": "string", "description": "Target country code such as US"},
                "target_store": {"type": "string", "description": "Optional store ref or display name"},
                "visibility_mode": {"type": "string", "description": "backend_only or sell_immediately"},
                "rules": {
                    "type": "object",
                    "description": "Shared rules applied to all items (can be overridden per-item in batch mode).",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_import_preview",
        description="Load a previously prepared preview bundle by job_id.",
        inputSchema={
            "type": "object",
            "properties": {"job_id": {"type": "string", "description": "Prepared job id"}},
            "required": ["job_id"],
        },
    ),
    Tool(
        name="set_product_visibility",
        description="Update the requested visibility mode for a prepared job before confirmation.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Prepared job id"},
                "visibility_mode": {"type": "string", "description": "backend_only or sell_immediately"},
            },
            "required": ["job_id", "visibility_mode"],
        },
    ),
    Tool(
        name="confirm_push_to_store",
        description=(
            "Push prepared drafts to store(s). Supports three modes: "
            "(1) Single: job_id + target_store; "
            "(2) Batch: job_ids list, each processed independently; "
            "(3) Multi-store: target_stores list, one job pushed to N stores. "
            "Batch + multi-store combines as N jobs x M stores."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Single job id (single mode)"},
                "job_ids": {
                    "type": "array",
                    "description": (
                        "Batch mode: list of job IDs. Each item can be a plain string "
                        "or an object {job_id, target_store?, target_stores?, push_options?, visibility_mode?} "
                        "for per-item overrides. When present, job_id is ignored."
                    ),
                    "items": {},
                },
                "target_store": {"type": "string", "description": "Target store (shared across all items)"},
                "target_stores": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Push to multiple stores. Each job is pushed to every store in this list.",
                },
                "visibility_mode": {"type": "string", "description": "backend_only or sell_immediately"},
                "push_options": {
                    "type": "object",
                    "description": "Provider-neutral publish settings (shared, can be overridden per-item).",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_job_status",
        description="Get the current status for a prepared or pushed job.",
        inputSchema={
            "type": "object",
            "properties": {"job_id": {"type": "string", "description": "Prepared job id"}},
            "required": ["job_id"],
        },
    ),
]


# ──────────────────────────────────────────────────────────────
#  Handler dispatch / 处理器分发
# ──────────────────────────────────────────────────────────────

_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
    "get_rule_capabilities": SERVICE.get_rule_capabilities,
    "validate_rules": SERVICE.validate_rules,
    "prepare_import_candidate": SERVICE.prepare_import_candidate,
    "get_import_preview": SERVICE.get_import_preview,
    "set_product_visibility": SERVICE.set_product_visibility,
    "confirm_push_to_store": SERVICE.confirm_push_to_store,
    "get_job_status": SERVICE.get_job_status,
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    handler = _HANDLERS.get(name)
    if handler is None:
        return _reply_json({"error": "Unknown tool", "available": sorted(_HANDLERS)})

    try:
        data = await handler(arguments or {})
        return _reply_json(data)
    except Exception as exc:
        return _reply_json({"error": str(exc)})


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
