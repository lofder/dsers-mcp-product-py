"""
Mock Import Provider — Deterministic stub for testing and development.
模拟导入提供者 —— 用于测试和开发的确定性桩模块

Returns hard-coded sample data so the full import flow can be exercised
without any real platform credentials. Useful for:
  - CI pipelines that validate the protocol layer
  - Local development when the private adapter is unavailable
  - Demonstrating the MCP workflow to new contributors

返回硬编码的示例数据，使完整的导入流程无需真实平台凭据即可运行。适用于：
  - CI 流水线中验证协议层
  - 私有适配器不可用时的本地开发
  - 向新贡献者演示 MCP 工作流
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from dsers_mcp_product.provider import ImportProvider


# Sample product used by the mock provider for all imports.
# 模拟提供者在所有导入中使用的示例商品。
_SAMPLE_DRAFT = {
    "title": "Sample Wireless Charger",
    "description_html": "<p>Sample product prepared by the mock provider.</p>",
    "images": [
        "https://example.com/images/mock-1.jpg",
        "https://example.com/images/mock-2.jpg",
        "https://example.com/images/mock-3.jpg",
    ],
    "tags": ["mock", "wireless", "charger"],
    "variants": [
        {
            "variant_ref": "mock-variant-1",
            "title": "Black / Standard",
            "supplier_price": 4.2,
            "offer_price": 8.9,
            "sku": "MOCK-BLK-STD",
            "image_url": "https://example.com/images/mock-1.jpg",
        },
        {
            "variant_ref": "mock-variant-2",
            "title": "White / Standard",
            "supplier_price": 4.4,
            "offer_price": 9.1,
            "sku": "MOCK-WHT-STD",
            "image_url": "https://example.com/images/mock-2.jpg",
        },
    ],
}


class MockImportProvider(ImportProvider):
    """
    A provider that always succeeds with deterministic sample data.
    一个始终返回确定性示例数据的提供者。

    TODO(PY-P3-02): Add error simulation support — e.g. a flag to trigger
    specific error codes (AUTH_REQUIRED, LIMIT_EXCEEDED) so integration
    tests can exercise error-handling paths.
    """

    name = "mock"

    async def get_rule_capabilities(self, target_store: Optional[str] = None) -> Dict[str, Any]:
        """
        Advertise broad capabilities so all rule families can be tested.
        声明广泛的能力，使所有规则族都可以被测试。
        """
        return {
            "provider_label": "Mock Provider",
            "source_support": ["aliexpress", "accio_best_effort"],
            "stores": [
                {"store_ref": "mock-store-1", "display_name": "Mock Store 1"},
                {"store_ref": "mock-store-2", "display_name": "Mock Store 2"},
            ],
            "rule_families": {
                "pricing": {
                    "supported": True,
                    "modes": ["provider_default", "multiplier", "fixed_markup"],
                },
                "content": {
                    "supported": [
                        "title_override",
                        "title_prefix",
                        "title_suffix",
                        "description_override_html",
                        "description_append_html",
                        "tags_add",
                    ],
                },
                "images": {
                    "supported": ["keep_first_n", "drop_indexes"],
                    "unsupported": ["translate_image_text", "remove_logo"],
                },
                "visibility": {
                    "supported_modes": ["backend_only", "sell_immediately"],
                },
            },
            "push_options": {
                "supported": [
                    "publish_to_online_store",
                    "only_push_specifications",
                    "image_strategy",
                    "pricing_rule_behavior",
                    "auto_inventory_update",
                    "auto_price_update",
                    "sales_channels",
                ],
                "image_strategy_modes": ["selected_only", "all_available"],
                "pricing_rule_behavior_modes": ["keep_manual", "apply_store_pricing_rule"],
                "sales_channels": ["online_store", "shop_app", "google_youtube", "tiktok", "facebook_instagram"],
            },
            "target_store": target_store,
        }

    async def prepare_candidate(
        self,
        source_url: str,
        source_hint: str,
        country: str,
    ) -> Dict[str, Any]:
        """
        Return a deep copy of the sample draft as the import candidate.
        返回示例草稿的深拷贝作为导入候选项。
        """
        return {
            "provider_state": {
                "candidate_ref": "mock-candidate-1",
                "source_hint": source_hint,
                "country": country,
            },
            "draft": deepcopy(_SAMPLE_DRAFT),
            "warnings": [],
            "resolved_source": source_url,
        }

    async def commit_candidate(
        self,
        provider_state: Dict[str, Any],
        draft: Dict[str, Any],
        target_store: Optional[str],
        visibility_mode: str,
        push_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Simulate a successful push — no real side effects.
        模拟推送成功 —— 没有真实的副作用。
        """
        return {
            "provider_label": "Mock Provider",
            "job_status": "pushed",
            "visibility_requested": visibility_mode,
            "visibility_applied": visibility_mode,
            "push_options_applied": push_options,
            "target_store": target_store or "mock-store-1",
            "warnings": [],
            "summary": {
                "title": draft.get("title"),
                "image_count": len(draft.get("images") or []),
                "variant_count": len(draft.get("variants") or []),
            },
            "provider_state": provider_state,
        }


    async def find_products(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "items": [
                {
                    "product_id": "1005001234567890",
                    "title": "Sample Phone Case",
                    "image": "https://example.com/phone-case.jpg",
                    "min_price": 150,
                    "max_price": 350,
                    "rating": 4.8,
                    "orders": 1200,
                    "logistics_cost": 0,
                    "app_id": "159831080",
                }
            ],
            "search_after": "",
        }

    async def list_import_items(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "items": [
                {
                    "import_item_id": "mock-import-1",
                    "title": "Sample Wireless Charger",
                    "sell_price_range": "$8.90 – $9.10",
                    "cost_range": "$4.20 – $4.40",
                    "variant_count": 2,
                    "total_stock": 1000,
                    "push_status": "not_pushed",
                }
            ],
            "total": 1,
        }

    async def list_my_products(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"items": [], "total": 0}

    async def delete_import_item(self, import_item_id: str) -> Dict[str, Any]:
        return {"deleted": True}

    async def save_draft(self, provider_state: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
        return {"warnings": []}


def build_provider() -> ImportProvider:
    """
    Factory function required by the provider loader.
    提供者加载器所需的工厂函数。
    """
    return MockImportProvider()
