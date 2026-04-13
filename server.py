#!/usr/bin/env python3
"""
DSers MCP Product Server — Entry point for the product import workflow.
DSers MCP 商品服务器 —— 商品导入工作流的入口点

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
from mcp.types import CallToolResult, TextContent, Tool

from dsers_mcp_product.job_store import FileJobStore
from dsers_mcp_product.provider import load_provider
from dsers_mcp_product.service import ImportFlowService

load_dotenv()

# Job state directory — each import job is persisted as a JSON file here.
# 任务状态目录 —— 每个导入任务以 JSON 文件形式持久化在此目录。
# PY-P2-05: Tool names intentionally differ from the TypeScript version
# (e.g. prepare_import_candidate vs dsers_product_import) — this is by design
# to match Python naming conventions while the TS version follows DSers API conventions.
STATE_DIR = Path(os.getenv("IMPORT_MCP_STATE_DIR") or Path.home() / ".dsers-mcp" / "state")

# Provider and service are instantiated once at startup.
# 提供者和服务在启动时实例化一次。
PROVIDER = load_provider()
SERVICE = ImportFlowService(PROVIDER, FileJobStore(STATE_DIR))

app = Server("dsers-mcp-product")


def _reply_json(data: Any) -> list[TextContent]:
    """Wrap any data as a JSON TextContent response. / 将任何数据包装为 JSON TextContent 响应。"""
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


# ──────────────────────────────────────────────────────────────
#  Tool definitions / 工具定义
# ──────────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="get_rule_capabilities",
        title="Store & Rule Discovery",
        description=(
            "Retrieve available stores, supported rule families (pricing, content, images), push options, and visibility modes "
            "for the connected DSers account. Call this first before any other tool — the response contains store IDs, "
            "shipping profiles, and configuration constraints needed by all subsequent operations. "
            "Returns: provider_label, source_support (aliexpress/alibaba/1688), stores (each with store_ref, display_name, "
            "platform, shipping_profiles), rule_families, push_options, notes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "target_store": {
                    "type": "string",
                    "description": (
                        "Store ID or display name to filter capabilities for a specific store. "
                        "Omit to see all linked stores. Use the store_ref or display_name from this response in later calls."
                    ),
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="validate_rules",
        title="Rule Validation",
        description=(
            "Check and normalize a rules object against the provider's capabilities before importing. "
            "Use this to verify pricing, content, and image rules are valid and see exactly which ones will be applied. "
            "Returns: effective_rules_snapshot (what will actually be applied), warnings (adjustments made), "
            "errors (blocking issues that must be fixed before calling prepare_import_candidate)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "target_store": {
                    "type": "string",
                    "description": "Store ID or display name from get_rule_capabilities. Some rule capabilities vary by store.",
                },
                "rules": {
                    "type": "object",
                    "description": (
                        "Structured rule object. Top-level keys: pricing, content, images."
                    ),
                    "properties": {
                        "pricing": {
                            "type": "object",
                            "description": "Pricing rules to apply to variants.",
                            "properties": {
                                "mode": {
                                    "type": "string",
                                    "enum": ["provider_default", "multiplier", "fixed_markup"],
                                    "description": "Pricing mode. provider_default: keep original prices. multiplier: multiply supplier price. fixed_markup: add fixed amount.",
                                },
                                "multiplier": {"type": "number", "description": "Price multiplier (required when mode=multiplier). Example: 2.5"},
                                "fixed_markup": {"type": "number", "description": "Fixed amount to add (required when mode=fixed_markup). Example: 5.00"},
                                "round_digits": {"type": "integer", "description": "Decimal places to round to. Default: 2"},
                            },
                        },
                        "content": {
                            "type": "object",
                            "description": "Product content modifications.",
                            "properties": {
                                "title_override": {"type": "string", "description": "Replace the entire product title."},
                                "title_prefix": {"type": "string", "description": "Prepend to the product title. Example: '[US] '"},
                                "title_suffix": {"type": "string", "description": "Append to the product title."},
                                "description_override_html": {"type": "string", "description": "Replace the entire product description (HTML)."},
                                "description_append_html": {"type": "string", "description": "Append HTML to the existing description."},
                                "tags_add": {"type": "array", "items": {"type": "string"}, "description": "Tags to add to the product."},
                            },
                        },
                        "images": {
                            "type": "object",
                            "description": "Image selection rules.",
                            "properties": {
                                "keep_first_n": {"type": "integer", "description": "Keep only the first N images. Example: 5"},
                                "drop_indexes": {"type": "array", "items": {"type": "integer"}, "description": "0-based image indexes to remove. Applied before keep_first_n."},
                            },
                        },
                    },
                },
            },
            "required": ["rules"],
        },
    ),
    Tool(
        name="prepare_import_candidate",
        title="Import Products",
        description=(
            "Import product(s) from supplier URL(s) into the DSers import list and return a preview bundle with title, "
            "prices, images, and variants. Single mode: provide source_url. Batch mode: provide source_urls with an array. "
            "Each successful import returns a job_id needed for get_import_preview, set_product_visibility, and confirm_push_to_store. "
            "Returns: job_id, status, title_before/after, price_range_before/after, images_before/after, variant_count, "
            "variant_preview (first 5), warnings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "source_url": {
                    "type": "string",
                    "description": (
                        "Single supplier product URL. Supports AliExpress (aliexpress.com/item/xxx.html), "
                        "Alibaba (alibaba.com/product-detail/xxx.html), and 1688 (1688.com/offer/xxx.html)."
                    ),
                },
                "source_urls": {
                    "type": "array",
                    "description": (
                        "Batch import: list of URL strings or objects with {url, source_hint?, country?, target_store?, "
                        "visibility_mode?, rules?} for per-item overrides. When present, source_url is ignored."
                    ),
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "object", "properties": {
                                "url": {"type": "string"},
                                "source_hint": {"type": "string"},
                                "country": {"type": "string"},
                                "target_store": {"type": "string"},
                                "rules": {"type": "object"},
                            }, "required": ["url"]},
                        ],
                    },
                },
                "source_hint": {
                    "type": "string",
                    "enum": ["auto", "aliexpress", "alibaba", "1688", "accio"],
                    "description": "Supplier platform hint. Default: auto (detected from URL).",
                },
                "country": {"type": "string", "description": "Target country code for shipping and pricing lookup. Examples: US, GB, DE, FR, AU."},
                "target_store": {
                    "type": "string",
                    "description": "Store ID or display name from get_rule_capabilities. Required when the account has multiple stores.",
                },
                "visibility_mode": {
                    "type": "string",
                    "enum": ["backend_only", "sell_immediately"],
                    "description": (
                        "Product visibility after push. "
                        "backend_only: saved as draft, not visible to shoppers. "
                        "sell_immediately: published and visible on the storefront."
                    ),
                },
                "rules": {
                    "type": "object",
                    "description": (
                        "Shared rules applied to all items (can be overridden per-item in batch mode). "
                        "Keys: pricing ({mode, multiplier, fixed_markup, round_digits}), "
                        "content ({title_override, title_prefix, title_suffix, description_override_html, description_append_html, tags_add}), "
                        "images ({keep_first_n, drop_indexes})."
                    ),
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_import_preview",
        title="View Import Preview",
        description=(
            "Reload the preview for a previously prepared import job without re-importing. "
            "Use this to re-examine title, prices, images, variants, and applied rules for a job created by prepare_import_candidate. "
            "Returns the same structure as prepare_import_candidate: job_id, status, title, price ranges, images, variants, rules, warnings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by prepare_import_candidate."},
            },
            "required": ["job_id"],
        },
    ),
    Tool(
        name="set_product_visibility",
        title="Set Visibility",
        description=(
            "Change the visibility mode of a prepared job before pushing it to the store. "
            "Call this between prepare_import_candidate and confirm_push_to_store to switch between draft and published. "
            "Returns: job_id, status, visibility_mode."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID returned by prepare_import_candidate."},
                "visibility_mode": {
                    "type": "string",
                    "enum": ["backend_only", "sell_immediately"],
                    "description": (
                        "New visibility mode. "
                        "backend_only: save as draft, not visible to shoppers. "
                        "sell_immediately: publish to storefront."
                    ),
                },
            },
            "required": ["job_id", "visibility_mode"],
        },
    ),
    Tool(
        name="confirm_push_to_store",
        title="Push to Store",
        description=(
            "Push one or more prepared import drafts to the connected Shopify store(s). "
            "Three modes: (1) Single push — provide job_id + target_store. "
            "(2) Batch push — provide job_ids with an array of job IDs or objects; takes priority over job_id. "
            "(3) Multi-store push — provide job_id + target_stores to push one product to multiple stores. "
            "Returns per-job results: job_id, status, target_store, visibility_applied, push_options_applied, job_summary, warnings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Single job ID from prepare_import_candidate. Used for single-push or multi-store mode.",
                },
                "job_ids": {
                    "type": "array",
                    "description": (
                        "Batch push: list of job ID strings or objects "
                        "{job_id, target_store?, target_stores?, push_options?, visibility_mode?}. "
                        "When provided, this takes priority over job_id."
                    ),
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "object", "properties": {
                                "job_id": {"type": "string"},
                                "target_store": {"type": "string"},
                                "target_stores": {"type": "array", "items": {"type": "string"}},
                                "push_options": {"type": "object"},
                                "visibility_mode": {"type": "string"},
                            }, "required": ["job_id"]},
                        ],
                    },
                },
                "target_store": {
                    "type": "string",
                    "description": "Target store ID or display name from get_rule_capabilities. Required when the account has multiple stores.",
                },
                "target_stores": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multi-store: list of store IDs or display names. Pushes the same job_id to each listed store.",
                },
                "visibility_mode": {
                    "type": "string",
                    "enum": ["backend_only", "sell_immediately"],
                    "description": "Override the visibility mode set during prepare. backend_only: draft. sell_immediately: published.",
                },
                "push_options": {
                    "type": "object",
                    "description": "Push configuration (shared, can be overridden per-item in batch mode).",
                    "properties": {
                        "publish_to_online_store": {"type": "boolean", "description": "Auto-derived from visibility_mode. Override only if needed."},
                        "image_strategy": {
                            "type": "string",
                            "enum": ["selected_only", "all_available"],
                            "description": "Which images to push. selected_only: only import-list images. all_available: all supplier images.",
                        },
                        "pricing_rule_behavior": {
                            "type": "string",
                            "enum": ["keep_manual", "apply_store_pricing_rule"],
                            "description": "keep_manual: use prices from the draft. apply_store_pricing_rule: apply the store's DSers pricing rule.",
                        },
                        "shipping_profile_name": {
                            "type": "string",
                            "description": "Shopify delivery profile name (e.g. 'DSers Shipping Profile'). If omitted, the default profile is used.",
                        },
                        "auto_inventory_update": {"type": "boolean", "description": "Enable automatic inventory sync after push. Default: false."},
                        "auto_price_update": {"type": "boolean", "description": "Enable automatic price sync after push. Default: false."},
                        "sales_channels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Shopify sales channels to publish to. Examples: online_store, shop_app, google_youtube, tiktok.",
                        },
                        "only_push_specifications": {"type": "boolean", "description": "Push only variant specs without images/descriptions. Default: false."},
                    },
                },
                "force_push": {
                    "type": "boolean",
                    "description": "Override pre-push safety checks. ONLY set true after showing the user the specific risk and getting explicit consent.",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_job_status",
        title="Check Job Status",
        description=(
            "Check the current status of an import or push job. "
            "Status lifecycle: preview_ready (after prepare) -> push_requested (after confirm) -> completed or failed. "
            "Call this to monitor push progress or verify a job's state before further action. "
            "Returns: job_id, status, created_at, updated_at, target_store, visibility_mode, warnings, has_push_result."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID from prepare_import_candidate or confirm_push_to_store."},
            },
            "required": ["job_id"],
        },
    ),
    # ── Rule update tool (v1.5) ──
    Tool(
        name="dsers_product_update_rules",
        title="Update Product Rules",
        description=(
            "Update pricing, content, images, or variant rules on an already-imported product. "
            "Rules are merged incrementally: pricing/images/variant_overrides replace by family; "
            "content merges by field. To clear a content field, send empty string. To remove an entire family, pass null. "
            "If rule persistence to DSers backend fails, job status is set to persist_failed and subsequent push will be blocked."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID from prepare_import_candidate."},
                "rules": {"type": "object", "description": "Rules object (pricing, content, images, variant_overrides, option_edits)."},
                "target_store": {"type": "string", "description": "Target store ID or name."},
                "visibility_mode": {"type": "string", "description": "backend_only or sell_immediately."},
            },
            "required": ["job_id"],
        },
    ),
    # ── Browse / search tools (v1.5) ──
    Tool(
        name="dsers_find_product",
        title="Search DSers Product Pool",
        description=(
            "Search the DSers product pool (AliExpress supplier catalog) for products to import by keyword or image URL. "
            "Returns products that can be directly imported via prepare_import_candidate using the import_url field. "
            "Use search_after from the response to get the next page. "
            "Note: results may overlap between pages — deduplicate by product_id if needed. "
            "Empty or whitespace-only keywords are rejected."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search keyword. Omit when using image_url."},
                "image_url": {"type": "string", "description": "Image URL for visual search. Mutually exclusive with keyword."},
                "limit": {"type": "integer", "default": 20, "description": "Results per page (max 50)"},
                "search_after": {"type": "string", "description": "Cursor from previous response for pagination"},
                "sort": {"type": "string", "enum": ["relevance", "newest", "price"], "description": "Sort order"},
                "ship_to": {"type": "string", "default": "US", "description": "Destination country code"},
                "ship_from": {"type": "string", "description": "Origin country code (CN, US, FR, UK)"},
                "category_id": {"type": "string", "description": "Category ID filter"},
            },
        },
    ),
    Tool(
        name="dsers_import_list",
        title="Browse Import List",
        description=(
            "Browse the DSers import list with enriched variant data. "
            "Returns per item: import_item_id, title, sell_price_range, cost_range, variant_count, total_stock, push_status. "
            "This is the staging area before push. To see products already on your store, use dsers_my_products."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1, "description": "Page number (1-based)."},
                "page_size": {"type": "integer", "default": 20, "description": "Items per page. Max: 100."},
            },
        },
    ),
    Tool(
        name="dsers_my_products",
        title="Browse My Products",
        description=(
            "Browse products already pushed to a store. Requires store_id (from get_rule_capabilities). "
            "Returns: dsers_product_id, title, sell_price, cost, status, supplier, supplier_url."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "store_id": {"type": "string", "description": "Store ID from get_rule_capabilities. Required."},
                "page": {"type": "integer", "default": 1, "description": "Page number."},
                "page_size": {"type": "integer", "default": 20, "description": "Items per page. Max: 100."},
            },
            "required": ["store_id"],
        },
    ),
    Tool(
        name="dsers_product_delete",
        title="Delete Import List Item",
        description=(
            "Permanently delete a product from the DSers import list. IRREVERSIBLE. "
            "Requires confirm=true to execute. Products already pushed to stores are NOT affected. "
            "First call without confirm to get a confirmation prompt."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "import_item_id": {"type": "string", "description": "Import item ID from dsers_import_list or dsers_product_preview."},
                "confirm": {"type": "boolean", "default": False, "description": "Set true to confirm deletion."},
            },
            "required": ["import_item_id"],
        },
    ),
    # ── SKU remap tool (v1.5) ──
    Tool(
        name="dsers_sku_remap",
        title="Replace Supplier (SKU Remap)",
        description=(
            "Replace the supplier on a store product with SKU-level variant matching. "
            "Defaults to mode=preview (read-only). Two paths: "
            "(A) STRICT — provide new_supplier_url to swap to that exact supplier. "
            "(B) DISCOVER — omit new_supplier_url to auto-find the best replacement via image search. "
            "Returns: path, summary (swapped/kept_old/unmatched), diffs, and optionally top_candidates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "dsers_product_id": {"type": "string", "description": "DSers product ID of the store product."},
                "store_id": {"type": "string", "description": "Store ID from get_rule_capabilities."},
                "new_supplier_url": {"type": "string", "description": "Optional. AliExpress/Alibaba URL of replacement supplier."},
                "mode": {"type": "string", "enum": ["preview", "apply"], "default": "preview", "description": "preview (read-only) or apply (persist)."},
                "country": {"type": "string", "default": "US", "description": "Target country code."},
                "auto_confidence": {"type": "integer", "default": 70, "description": "Minimum match confidence 0-100."},
                "max_candidates": {"type": "integer", "default": 5, "description": "Max candidates for discover mode."},
            },
            "required": ["dsers_product_id", "store_id"],
        },
    ),
]


# ──────────────────────────────────────────────────────────────
#  Handler dispatch / 处理器分发
# ──────────────────────────────────────────────────────────────

async def _handle_sku_remap(params: Dict[str, Any]) -> Dict[str, Any]:
    from dsers_mcp_product.sku_remap_service import sku_remap
    return await sku_remap(PROVIDER, SERVICE._store, params)

async def _handle_find_product(params: Dict[str, Any]) -> Dict[str, Any]:
    from dsers_mcp_product.browse_service import discover_products
    return await discover_products(PROVIDER, params)

async def _handle_import_list(params: Dict[str, Any]) -> Dict[str, Any]:
    from dsers_mcp_product.browse_service import browse_import_list
    return await browse_import_list(PROVIDER, params)

async def _handle_my_products(params: Dict[str, Any]) -> Dict[str, Any]:
    from dsers_mcp_product.browse_service import browse_my_products
    return await browse_my_products(PROVIDER, params)

async def _handle_product_delete(params: Dict[str, Any]) -> Dict[str, Any]:
    from dsers_mcp_product.browse_service import delete_import_item
    return await delete_import_item(PROVIDER, params)

_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
    "get_rule_capabilities": SERVICE.get_rule_capabilities,
    "validate_rules": SERVICE.validate_rules,
    "prepare_import_candidate": SERVICE.prepare_import_candidate,
    "get_import_preview": SERVICE.get_import_preview,
    "set_product_visibility": SERVICE.set_product_visibility,
    "confirm_push_to_store": SERVICE.confirm_push_to_store,
    "get_job_status": SERVICE.get_job_status,
    "dsers_product_update_rules": SERVICE.update_rules,
    "dsers_find_product": _handle_find_product,
    "dsers_import_list": _handle_import_list,
    "dsers_my_products": _handle_my_products,
    "dsers_product_delete": _handle_product_delete,
    "dsers_sku_remap": _handle_sku_remap,
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    handler = _HANDLERS.get(name)
    if handler is None:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {name}")],
            isError=True,
        )

    try:
        data = await handler(arguments or {})
        return CallToolResult(content=_reply_json(data), isError=False)
    except Exception as exc:
        from dsers_mcp_product.security import sanitize_error
        return CallToolResult(
            content=[TextContent(type="text", text=sanitize_error(str(exc)))],
            isError=True,
        )


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import signal
    import sys
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    asyncio.run(main())
