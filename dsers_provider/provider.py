"""
Private DSers Provider — Concrete ImportProvider for the DSers platform.
私有 DSers 提供者 —— DSers 平台的具体 ImportProvider 实现

This adapter dynamically loads the vendor-dsers library at init time and
wires up the DSers account / product / settings handlers. It translates
the normalised import draft (title, variants, images) back into the raw
field structure that the DSers backend expects, handling edge cases like:
  - Multiple URL formats (AliExpress, Alibaba, 1688)
  - Variant price de-normalisation with original field keys
  - Store shipping profile attachment for Shopify
  - Shipping template & logistics resolution

本适配器在初始化时动态加载 vendor-dsers 库，并连接 DSers 的账户/商品/
设置处理器。它将标准化的导入草稿（标题、变体、图片）反向转换为 DSers
后端期望的原始字段结构，处理以下边缘情况：
  - 多种 URL 格式（AliExpress、Alibaba、1688）
  - 使用原始字段键反标准化变体价格
  - 为 Shopify 附加店铺配送档案
  - 运输模板与物流方式解析
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from dsers_mcp_product.provider import ImportProvider

# ──────────────────────────────────────────────────────────────
#  Constants / 常量
# ──────────────────────────────────────────────────────────────

# Default source app IDs used by DSers to identify supplier platforms.
# DSers 用于识别供应商平台的默认来源应用 ID。
DEFAULT_ALIEXPRESS_APP_ID = "159831080"
DEFAULT_ALIBABA_APP_ID = "1902659021782450176"

# Shopify sales channels supported for the push request.
# 推送请求支持的 Shopify 销售渠道。
DEFAULT_PUSH_CHANNELS = [
    "online_store",
    "shop_app",
    "google_youtube",
    "tiktok",
    "facebook_instagram",
    "amazon",
]

# Regex patterns to extract numeric product IDs from supplier URLs.
# 从供应商 URL 中提取数字商品 ID 的正则表达式。
ALIEXPRESS_ID_PATTERN = re.compile(r"/item/(\d+)\.html", re.IGNORECASE)
ALIBABA_ID_PATTERN = re.compile(r"/product-detail/[^_]+_(\d+)\.html", re.IGNORECASE)
ALI1688_ID_PATTERN = re.compile(r"1688\.com/(?:offer|product-detail)/(\d+)\.html", re.IGNORECASE)


class PrivateDsersProvider(ImportProvider):
    """
    Concrete adapter that implements the ImportProvider contract using DSers APIs.
    使用 DSers API 实现 ImportProvider 契约的具体适配器。

    Architecture: this class sits between the public protocol layer and the
    vendor-dsers library. It never exposes raw DSers API names to the caller.

    架构：此类位于公开协议层和 vendor-dsers 库之间，
    不会向调用方暴露原始的 DSers API 名称。
    """

    name = "private-dsers"

    def __init__(self) -> None:
        """
        Bootstrap the DSers adapter: load env, locate vendor-dsers,
        instantiate the shared HTTP client, and register module handlers.

        引导 DSers 适配器：加载环境变量、定位 vendor-dsers 库、
        实例化共享 HTTP 客户端、注册各模块处理器。
        """
        load_dotenv()
        self._vendor_dir = Path(
            os.getenv(
                "DSERS_PROVIDER_LIB_DIR",
                str(Path(__file__).resolve().parents[1] / "vendor-dsers"),
            )
        ).resolve()
        if not self._vendor_dir.exists():
            raise RuntimeError(f"DSers vendor library directory not found: {self._vendor_dir}")

        session_file = Path(
            os.getenv(
                "PRIVATE_DSERS_SESSION_FILE",
                str(Path(__file__).resolve().parents[1] / ".session-cache" / "dsers-test-session.json"),
            )
        ).resolve()
        session_file.parent.mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("DSERS_ENV", "production")
        os.environ.setdefault("DSERS_SESSION_FILE", str(session_file))

        if str(self._vendor_dir) not in sys.path:
            sys.path.insert(0, str(self._vendor_dir))

        config_mod = importlib.import_module("dsers_mcp_base.config")
        client_mod = importlib.import_module("dsers_mcp_base.client")
        account_mod = importlib.import_module("dsers_account")
        product_mod = importlib.import_module("dsers_product")
        settings_mod = importlib.import_module("dsers_settings")

        config = config_mod.DSersConfig.from_env()
        client = client_mod.DSersClient(config)

        _, self._account_handler = account_mod.register(None, client)
        _, self._product_handler = product_mod.register(None, client)
        _, self._settings_handler = settings_mod.register(None, client)

        self._aliexpress_app_id = int(os.getenv("PRIVATE_DSERS_ALIEXPRESS_APP_ID", DEFAULT_ALIEXPRESS_APP_ID))
        self._alibaba_app_id = int(os.getenv("PRIVATE_DSERS_ALIBABA_APP_ID", DEFAULT_ALIBABA_APP_ID))

    # ── ImportProvider interface / ImportProvider 接口实现 ──

    async def get_rule_capabilities(self, target_store: Optional[str] = None) -> Dict[str, Any]:
        """
        Query linked stores and declare which rules, push options, and
        visibility modes this adapter supports.  For Shopify stores, also
        fetches available delivery profiles so the caller can display them
        and optionally let the user choose one by name.

        查询已关联店铺，声明此适配器支持的规则、推送选项和可见性模式。
        对于 Shopify 店铺，还会获取可用的 Delivery Profile 列表，
        供调用方展示给用户选择。
        """
        stores = await self._list_stores()
        stores = await self._enrich_shopify_profiles(stores)
        visibility_modes = ["backend_only", "sell_immediately"]

        notes = [
            "Provider-native pricing and auto-sync capabilities are available through the private adapter.",
            "Advanced image transformations are not auto-applied in this MVP.",
        ]
        if os.getenv("SHOPIFY_STORE_DOMAIN") and os.getenv("SHOPIFY_ADMIN_TOKEN"):
            notes.append("A separate Shopify fallback path is available in the environment if provider-native publish controls prove insufficient.")
        if target_store:
            notes.append(f"Target store hint received: {target_store}")

        return {
            "provider_label": "Private DSers Adapter",
            "source_support": ["aliexpress", "alibaba", "1688"],
            "stores": stores,
            "rule_families": {
                "pricing": {
                    "supported": True,
                    "modes": ["provider_default", "multiplier", "fixed_markup"],
                    "native_snapshot_available": True,
                },
                "content": {
                    "supported": [
                        "title_override",
                        "title_prefix",
                        "title_suffix",
                        "description_override_html",
                        "description_append_html",
                    ],
                    "unsupported": ["tags_add"],
                },
                "images": {
                    "supported": ["keep_first_n", "drop_indexes"],
                    "unsupported": ["translate_image_text", "remove_logo"],
                },
                "visibility": {
                    "supported_modes": visibility_modes,
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
                    "store_shipping_profile",
                    "shipping_profile_name",
                ],
                "image_strategy_modes": ["selected_only", "all_available"],
                "pricing_rule_behavior_modes": ["keep_manual", "apply_store_pricing_rule"],
                "sales_channels": DEFAULT_PUSH_CHANNELS,
                "shipping_profile_name_hint": (
                    "For Shopify stores, specify a delivery profile name "
                    "(e.g. 'DSers Shipping Profile') to override the default. "
                    "If omitted, the profile marked as default (isChecked) is used automatically."
                ),
            },
            "notes": notes,
        }

    async def prepare_candidate(
        self,
        source_url: str,
        source_hint: str,
        country: str,
    ) -> Dict[str, Any]:
        """
        Import pipeline: parse URL → resolve product ID → call DSers import API
        → fetch the draft → normalise into the standard schema.

        导入流水线：解析 URL → 提取商品 ID → 调用 DSers 导入 API
        → 获取草稿 → 标准化为统一 schema。
        """
        source_kind, app_id, supply_product_id = self._resolve_source_identifier(source_url)
        if not supply_product_id:
            parse_payload = await self._call(
                self._product_handler,
                "dsers_parse_product_url",
                {"url": source_url, "appId": app_id},
            )
            self._raise_if_error(parse_payload, "The private provider could not resolve the source URL in the current test environment.")
            supply_product_id = self._extract_supply_product_id(parse_payload)
        if not supply_product_id:
            raise RuntimeError("The private provider could not extract a supplier product id from the source URL.")

        import_payload = await self._call(
            self._product_handler,
            "dsers_import_by_product_id",
            {
                "supplyProductId": supply_product_id,
                "supplyAppId": app_id,
                "country": country,
            },
        )
        if self._has_reason(import_payload, "ALIBABA_NOT_AVAILABLE"):
            raise RuntimeError(
                "The selected Alibaba or 1688 product is recognized, but DSers reports it is currently not available for import."
            )
        if self._has_reason(import_payload, "PRODUCT_STATUS_NOT_ONSELLING"):
            raise RuntimeError(
                "The selected supplier product is recognized, but DSers reports it is not currently importable under the chosen source app."
            )
        already_exists = self._has_reason(import_payload, "IMPORT_LIST_PRODUCT_ALREADY_EXISTS")
        if not already_exists:
            self._raise_if_error(
                import_payload,
                f"The current test provider account is not authorized to import this {source_kind} source yet. Enable the source app in the test account first.",
            )

        import_item_id = self._extract_import_item_id(import_payload)
        if not import_item_id:
            import_item_id = await self._recover_import_item_id(supply_product_id)
        if not import_item_id:
            raise RuntimeError("The private provider could not recover the imported draft id.")

        item_payload = await self._call(self._product_handler, "dsers_get_import_list_item", {"id": import_item_id})
        self._raise_if_error(item_payload, "The private provider could not fetch the imported draft item.")
        draft, field_map, warnings = self._normalize_import_item(item_payload)

        provider_state = {
            "import_item_id": import_item_id,
            "source_hint": source_hint,
            "source_kind": source_kind,
            "source_app_id": app_id,
            "country": country,
            "field_map": field_map,
            "supply_product_id": supply_product_id,
        }

        return {
            "provider_label": "Private DSers Adapter",
            "provider_state": provider_state,
            "draft": draft,
            "warnings": warnings,
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
        Push pipeline: de-normalise draft → update import list item → resolve store
        → build push payload → attach shipping info → push → poll status.

        推送流水线：反标准化草稿 → 更新导入列表项 → 解析店铺
        → 构建推送 payload → 附加运输信息 → 推送 → 轮询状态。
        """
        field_map = provider_state.get("field_map") or {}
        warnings: List[str] = []
        pricing_rule_behavior = str(push_options.get("pricing_rule_behavior") or "keep_manual")

        update_args: Dict[str, Any] = {"id": provider_state["import_item_id"]}
        title_key = field_map.get("title_key") or "title"
        description_key = field_map.get("description_key") or "description"
        tags_key = field_map.get("tags_key")

        update_args[title_key] = draft.get("title")
        update_args[description_key] = draft.get("description_html")
        if tags_key:
            update_args[tags_key] = draft.get("tags") or []
        elif draft.get("tags"):
            warnings.append("Tag edits were skipped because the current test backend rejects raw tag writes for import-list items.")

        variants_key = field_map.get("variants_key")
        if variants_key and field_map.get("raw_variants"):
            update_args[variants_key] = self._denormalize_variants(draft.get("variants") or [], field_map)
            price_edit_flag_key = field_map.get("price_edit_flag_key")
            if price_edit_flag_key:
                update_args[price_edit_flag_key] = pricing_rule_behavior != "apply_store_pricing_rule"
            supply_key = field_map.get("supply_key")
            if supply_key and field_map.get("raw_supply"):
                update_args[supply_key] = self._denormalize_supply(draft.get("variants") or [], field_map)
            min_price_key = field_map.get("min_price_key")
            max_price_key = field_map.get("max_price_key")
            price_bounds = self._compute_price_bounds(draft.get("variants") or [])
            if min_price_key and price_bounds[0] is not None:
                update_args[min_price_key] = price_bounds[0]
            if max_price_key and price_bounds[1] is not None:
                update_args[max_price_key] = price_bounds[1]

        images_key = field_map.get("images_key")
        if images_key and field_map.get("images_mode") in {"string_list", "dict_list"}:
            update_args[images_key] = self._denormalize_images(draft.get("images") or [], field_map)
            main_image_key = field_map.get("main_image_key")
            if main_image_key:
                update_args[main_image_key] = (draft.get("images") or [None])[0]
        elif images_key and draft.get("images") is not None:
            warnings.append("Image edits were skipped because the private provider could not safely write the detected image structure.")

        update_payload = await self._call(self._product_handler, "dsers_update_import_list_item", update_args)
        self._raise_if_error(update_payload, "The private provider could not persist the prepared draft changes.")

        store = await self._resolve_store(target_store)
        push_args = self._build_push_arguments(
            import_item_id=provider_state["import_item_id"],
            store_ref=store["store_ref"],
            visibility_mode=visibility_mode,
            push_options=push_options,
        )
        warnings.extend(await self._refresh_product_shipping_info(provider_state))
        warnings.extend(await self._attach_shipping_template_logistics(provider_state, store["store_ref"], push_args))
        warnings.extend(await self._attach_store_shipping_profile(
            store, push_args, push_options, provider_state["import_item_id"],
        ))
        push_payload = await self._call(
            self._product_handler,
            "dsers_push_to_store",
            push_args,
        )
        self._raise_if_error(
            push_payload,
            "The private provider could not push the prepared draft to the selected store in the current test environment.",
        )
        event_id = self._find_first_value_by_keys(push_payload, ["event_id", "eventId", "id"])
        push_state = "requested"
        status_payload: Optional[Dict[str, Any]] = None
        if event_id:
            try:
                for attempt in range(4):
                    status_payload = await self._call(self._product_handler, "dsers_get_push_status", {"event_id": event_id})
                    push_state = self._extract_push_state(status_payload)
                    if push_state in {"failed", "completed"}:
                        break
                    if attempt < 3:
                        await asyncio.sleep(10)
            except Exception:
                warnings.append("Push status polling was skipped because the provider did not return a stable status payload.")
        if push_state == "failed":
            push_error = self._extract_push_error(status_payload or {})
            if push_error:
                warnings.append(f"Provider push failed: {push_error}")

        visibility_applied = "sell_immediately" if push_options.get("publish_to_online_store") else "backend_only"
        if visibility_mode == "sell_immediately" and not push_options.get("publish_to_online_store"):
            warnings.append("sell_immediately was requested, but publish_to_online_store resolved to false in push_options.")

        return {
            "provider_label": "Private DSers Adapter",
            "job_status": push_state,
            "event_id": event_id,
            "visibility_requested": visibility_mode,
            "visibility_applied": visibility_applied,
            "push_options_applied": push_options,
            "target_store": store.get("display_name") or store.get("store_ref"),
            "warnings": warnings,
            "summary": {
                "title": draft.get("title"),
                "image_count": len(draft.get("images") or []),
                "variant_count": len(draft.get("variants") or []),
            },
        }

    # ── Internal helpers / 内部辅助方法 ──

    async def _call(self, handler: Any, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        contents = await handler(name, arguments)
        text_parts = [item.text for item in contents if hasattr(item, "text")]
        if not text_parts:
            raise RuntimeError(f"Private provider received an empty response for {name}.")
        return json.loads("\n".join(text_parts))

    def _raise_if_error(self, payload: Dict[str, Any], generic_message: str) -> None:
        if isinstance(payload, dict) and payload.get("error"):
            detail = str(payload.get("detail") or payload.get("error"))
            if "PERMISSION_DENIED" in detail:
                raise RuntimeError(generic_message)
            raise RuntimeError(f"{generic_message} Provider detail: {payload.get('error')}")

    def _build_push_arguments(
        self,
        import_item_id: str,
        store_ref: str,
        visibility_mode: str,
        push_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assemble the raw push request payload matching the DSers web UI format.
        This structure was reverse-engineered from browser network captures.

        组装与 DSers 网页端格式一致的原始推送请求 payload。
        此结构通过浏览器网络抓包逆向工程获得。
        """
        import_list_id = self._coerce_numeric_id(import_item_id)
        store_id = self._coerce_numeric_id(store_ref)
        visible = bool(push_options.get("publish_to_online_store"))
        only_push_specifications = bool(push_options.get("only_push_specifications"))
        push_all_images = str(push_options.get("image_strategy") or "selected_only") == "all_available"
        with_price_rule = str(push_options.get("pricing_rule_behavior") or "keep_manual") == "apply_store_pricing_rule"
        auto_inventory_update = bool(push_options.get("auto_inventory_update"))
        auto_price_update = bool(push_options.get("auto_price_update"))
        sales_channels = list(push_options.get("sales_channels") or [])

        request: Dict[str, Any] = {
            "importListIds": [import_list_id],
            "storeIds": [store_id],
            "visible": visible,
            "pushStatus": "ACTIVE" if visibility_mode == "sell_immediately" else "DRAFT",
            "inventoryPolicy": False,
            "onlyPushSpecifications": False,
            "isPushAllImage": push_all_images,
            "storeLanguageList": [{"storeId": store_id, "language": "EN"}],
            "pushProducts": [{"importListId": import_list_id, "pushLanguageCode": "EN"}],
            "skus": [],
            "stores": [],
            "saleChannels": sales_channels or [],
            "logistics": [
                {
                    "storeId": store_id,
                    "importListId": import_list_id,
                    "shipCost": "",
                    "logisticId": "",
                    "switch": True,
                }
            ],
            "pricingRuleImportListIds": [{"importListId": import_list_id, "storeId": store_id}],
        }
        if only_push_specifications:
            request["onlyPushSpecifications"] = True
        if with_price_rule:
            request["withPriceRule"] = True

        sync_setting: Dict[str, Any] = {
            "autoUpdateStock": auto_inventory_update,
            "autoUpdatePrice": auto_price_update,
            "handleUpdatePrice": auto_price_update,
        }
        request["myProductSyncSetting"] = sync_setting
        return request

    async def _refresh_product_shipping_info(self, provider_state: Dict[str, Any]) -> List[str]:
        """
        Re-save the user's shipping template before push to ensure it's active.
        在推送前重新保存用户的运输模板，确保其处于激活状态。
        """
        source_app_id = provider_state.get("source_app_id")
        if source_app_id in (None, ""):
            return []

        payload = await self._call(
            self._settings_handler,
            "dsers_get_product_shipping_info",
            {"supplierAppId": self._coerce_numeric_id(source_app_id)},
        )
        if isinstance(payload, dict) and payload.get("error"):
            return ["DSers product shipping config could not be loaded before refresh."]

        data = payload.get("data")
        if not isinstance(data, dict):
            return ["DSers product shipping config payload was empty before refresh."]

        shipping_info = data.get("shippingInfo")
        if not isinstance(shipping_info, dict) or not shipping_info:
            return ["DSers product shipping config did not include a reusable shippingInfo object."]

        enabled = data.get("status")
        warnings: List[str] = []
        if enabled is None:
            enabled = bool(shipping_info)
        elif not enabled:
            enabled = True
            warnings.append("Enabled DSers product shipping config because a shipping template already exists.")

        update_payload = await self._call(
            self._settings_handler,
            "dsers_update_product_shipping_info",
            {
                "status": bool(enabled),
                "shippingInfo": shipping_info,
            },
        )
        if isinstance(update_payload, dict) and update_payload.get("error"):
            warnings.append("DSers product shipping config refresh failed before push.")
            return warnings

        warnings.append("Refreshed DSers product shipping config before push.")
        return warnings

    async def _attach_shipping_template_logistics(
        self,
        provider_state: Dict[str, Any],
        store_ref: str,
        push_args: Dict[str, Any],
    ) -> List[str]:
        """
        Match a logistics service ID from the user's shipping template to
        the available push-logistics options, then inject it into push_args.

        将用户运输模板中的物流服务 ID 与可用的推送物流选项匹配，
        然后注入到 push_args 中。
        """
        if push_args.get("logistics"):
            return []

        source_app_id = provider_state.get("source_app_id")
        if source_app_id in (None, ""):
            return []

        import_list_id = self._coerce_numeric_id(provider_state.get("import_item_id"))
        store_id = self._coerce_numeric_id(store_ref)
        country = str(provider_state.get("country") or "").strip().upper()
        supply_product_id = str(provider_state.get("supply_product_id") or "").strip()

        service_ids, source_label, service_warnings = await self._get_template_service_ids(
            source_app_id=source_app_id,
            supply_product_id=supply_product_id,
            country=country,
        )
        warnings = list(service_warnings)
        if not service_ids:
            return warnings

        available_ids = await self._get_push_logistics_ids(import_list_id, store_id)
        selected_id = ""
        if available_ids:
            selected_id = next((item for item in service_ids if item in available_ids), "")
            if not selected_id:
                warnings.append(
                    "DSers returned push-logistics options for the selected store, but none matched the current shipping template."
                )
                return warnings
        else:
            selected_id = service_ids[0]

        push_args["logistics"] = [
            {
                "importListId": import_list_id,
                "storeId": store_id,
                "logisticId": selected_id,
            }
        ]
        applied_from = f" from {source_label}" if source_label else ""
        warnings.append(f"Applied DSers shipping template logistic '{selected_id}'{applied_from} to the push request.")
        return warnings

    async def _attach_store_shipping_profile(
        self,
        store: Dict[str, Any],
        push_args: Dict[str, Any],
        push_options: Dict[str, Any],
        import_item_id: Optional[str] = None,
    ) -> List[str]:
        """
        Attach Shopify DeliveryProfile to the push request. Without this,
        Shopify rejects the push with 'shipping profile not found'.

        Fallback chain:
          1. Shopify-specific delivery profile API (isChecked=true profile)
          2. push_options.store_shipping_profile manual override

        Non-Shopify platforms (Wix, WooCommerce, etc.) do not require this
        field and will skip the profile lookup entirely.

        将 Shopify DeliveryProfile 附加到推送请求。如果缺少此字段，
        Shopify 会以 'shipping profile not found' 拒绝推送。

        回退链：
          1. Shopify 专用 delivery profile API（取 isChecked=true 的 profile）
          2. push_options.store_shipping_profile 手动覆盖

        非 Shopify 平台（Wix、WooCommerce 等）不需要此字段，会完全跳过查询。
        """
        if push_args.get("storeShippingProfile"):
            return []

        store_ref = store.get("store_ref", "")
        store_domain = store.get("domain", "")
        store_name = store.get("display_name", store_ref)
        is_shopify = ".myshopify.com" in store_domain or str(store.get("platform") or "").lower() == "shopify"

        if not is_shopify:
            return []

        warnings: List[str] = []
        store_id = self._coerce_numeric_id(store_ref)
        profile_items: Optional[List[Dict[str, Any]]] = None

        desired_name = (push_options.get("shipping_profile_name") or "").strip()

        # Source 1: Shopify-specific delivery profile API.
        # GET /dsers-product-bff/import-list/shopify/shipping-profile/get
        # If shipping_profile_name is given, match by name; otherwise pick isChecked=true.
        try:
            profiles_by_store = await self._fetch_shopify_profiles()
            target_key = str(store_id)
            raw_profiles = profiles_by_store.get(target_key, [])

            if desired_name:
                for profile in raw_profiles:
                    if (profile.get("name") or "").strip().lower() == desired_name.lower():
                        profile_items = self._extract_profile_gids(profile, target_key)
                        if profile_items:
                            warnings.append(f"Matched shipping profile by name: '{desired_name}'.")
                        break
                if not profile_items:
                    available = [p.get("name", "") for p in raw_profiles]
                    warnings.append(
                        f"shipping_profile_name '{desired_name}' not found. "
                        f"Available profiles: {available}. Falling back to default."
                    )

            if not profile_items:
                for profile in raw_profiles:
                    if profile.get("isChecked"):
                        profile_items = self._extract_profile_gids(profile, target_key)
                        break
        except Exception:
            warnings.append("Could not query Shopify delivery profiles.")

        # Source 2: manual override from push_options.
        if not profile_items:
            fallback = push_options.get("store_shipping_profile")
            if isinstance(fallback, list) and fallback:
                profile_items = fallback
                warnings.append("Using store_shipping_profile from push_options (API returned empty).")

        if profile_items:
            push_args["storeShippingProfile"] = profile_items
            warnings.append("Attached Shopify delivery profile to the push request.")
        else:
            warnings.append(
                f"Shopify store '{store_name}' ({store_domain}) has no Delivery Profile "
                f"configured in DSers. The push will likely fail with 'shipping profile "
                f"not found'. To fix: open DSers web UI -> Settings -> Shipping -> configure "
                f"a Delivery Profile for this store, or provide store_shipping_profile "
                f"in push_options."
            )

        return warnings

    @staticmethod
    def _extract_profile_gids(
        profile: Dict[str, Any], store_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Build the storeShippingProfile payload item from a raw profile dict."""
        profile_id = profile.get("id", "")
        groups = profile.get("profileGroups") or []
        location_id = groups[0].get("id", "") if groups else ""
        if profile_id and location_id:
            return [{"storeId": store_id, "locationId": location_id, "profileId": profile_id}]
        return None

    async def _get_template_service_ids(
        self,
        source_app_id: Any,
        supply_product_id: str,
        country: str,
    ) -> Tuple[List[str], str, List[str]]:
        warnings: List[str] = []
        product_payload = await self._call(
            self._settings_handler,
            "dsers_get_product_ship_settings",
            {
                "supplierProductId": [supply_product_id] if supply_product_id else None,
                "supplierAppId": [self._coerce_numeric_id(source_app_id)],
            },
        )
        product_ids, product_scope = self._extract_product_ship_service_ids(product_payload, country)
        if product_ids:
            return product_ids, product_scope or "product shipping settings", warnings

        if isinstance(product_payload, dict) and product_payload.get("error"):
            warnings.append("DSers product-level shipping settings were unavailable; falling back to the user shipping template.")

        shipping_payload = await self._call(
            self._settings_handler,
            "dsers_get_product_shipping_info",
            {"supplierAppId": self._coerce_numeric_id(source_app_id)},
        )
        shipping_ids, shipping_scope = self._extract_shipping_template_service_ids(shipping_payload, country)
        if shipping_ids:
            return shipping_ids, shipping_scope or "shipping template", warnings

        if isinstance(shipping_payload, dict) and shipping_payload.get("error"):
            warnings.append("DSers user shipping template could not be loaded before push.")
        else:
            warnings.append("No DSers shipping template service was found for the selected source app and country.")
        return [], "", warnings

    async def _get_push_logistics_ids(self, import_list_id: Any, store_id: Any) -> List[str]:
        payload = await self._call(
            self._product_handler,
            "dsers_get_push_logistics",
            {
                "importListIds": [import_list_id],
                "storeIds": [store_id],
            },
        )
        if isinstance(payload, dict) and payload.get("error"):
            return []

        data = payload.get("data")
        if not isinstance(data, dict):
            return []

        target_store = str(store_id)
        ids: List[str] = []
        for import_payload in data.values():
            if not isinstance(import_payload, dict):
                continue
            for store_payload in import_payload.get("storeLogistics") or []:
                if not isinstance(store_payload, dict):
                    continue
                current_store_id = str(store_payload.get("storeId") or "")
                if current_store_id and current_store_id != target_store:
                    continue
                for item in store_payload.get("logistics") or []:
                    if not isinstance(item, dict):
                        continue
                    service_id = self._first_present(item, ["logisticId", "serviceId", "id"])
                    if service_id and str(service_id) not in ids:
                        ids.append(str(service_id))
        return ids

    def _extract_product_ship_service_ids(self, payload: Dict[str, Any], country: str) -> Tuple[List[str], str]:
        data = payload.get("data")
        if not isinstance(data, list):
            return [], ""

        candidates: List[Tuple[int, List[str], str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            freight_info = item.get("freightInfo") or []
            if not isinstance(freight_info, list):
                continue
            country_ids = self._pick_freight_service_ids(freight_info, country)
            if country_ids:
                candidates.append((2, country_ids, country or "product shipping settings"))
                continue
            global_ids = self._pick_freight_service_ids(freight_info, "GLOBAL")
            if global_ids:
                candidates.append((1, global_ids, "Global product shipping settings"))

        if not candidates:
            return [], ""
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1], candidates[0][2]

    def _extract_shipping_template_service_ids(self, payload: Dict[str, Any], country: str) -> Tuple[List[str], str]:
        data = payload.get("data")
        if not isinstance(data, dict):
            return [], ""

        shipping_info = data.get("shippingInfo")
        if not isinstance(shipping_info, dict):
            return [], ""

        candidates: List[Tuple[int, List[str], str]] = []
        for entry in shipping_info.get("shippingCountryList") or []:
            if not isinstance(entry, dict):
                continue
            entry_country = str(entry.get("country") or "").strip()
            score = 0
            if entry_country.upper() == country and country:
                score = 2
            elif entry_country.upper() == "GLOBAL":
                score = 1
            if not score:
                continue
            service_ids = self._extract_service_ids_from_country_entry(entry)
            if service_ids:
                candidates.append((score, service_ids, entry_country or "shipping template"))

        if not candidates:
            return [], ""
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1], candidates[0][2]

    def _pick_freight_service_ids(self, freight_info: List[Any], country: str) -> List[str]:
        picked: List[str] = []
        for item in freight_info:
            if not isinstance(item, dict):
                continue
            ship_to = str(item.get("shipTo") or "").strip().upper()
            if ship_to != country:
                continue
            service_id = self._first_present(item, ["serviceId", "logisticId", "id"])
            if service_id and str(service_id) not in picked:
                picked.append(str(service_id))
        return picked

    def _extract_service_ids_from_country_entry(self, entry: Dict[str, Any]) -> List[str]:
        service_ids: List[str] = []
        for item in entry.get("list") or []:
            text = str(item or "").strip()
            if text and text not in service_ids:
                service_ids.append(text)
        for item in entry.get("logisticsInfo") or []:
            if not isinstance(item, dict):
                continue
            service_id = self._first_present(item, ["serviceId", "logisticId", "id"])
            if service_id and str(service_id) not in service_ids:
                service_ids.append(str(service_id))
        return service_ids

    def _has_reason(self, payload: Dict[str, Any], reason: str) -> bool:
        if not isinstance(payload, dict):
            return False
        detail = str(payload.get("detail") or payload.get("error") or "")
        return reason in detail

    def _coerce_numeric_id(self, value: Any) -> Any:
        text = str(value or "").strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return value

    async def _list_stores(self) -> List[Dict[str, Any]]:
        payload = await self._call(self._account_handler, "dsers_list_stores", {})
        store_dicts = self._extract_store_dicts(payload)
        stores = []
        for item in store_dicts:
            store_ref = self._first_present(item, ["storeId", "id", "sellerStoreId"])
            if not store_ref:
                continue
            domain = str(self._first_present(item, ["domain"]) or "")
            platform = self._first_present(item, ["platform", "storeType"])
            if not platform and ".myshopify.com" in domain:
                platform = "shopify"
            stores.append(
                {
                    "store_ref": str(store_ref),
                    "display_name": str(self._first_present(item, ["sellerName", "storeName", "name", "nickname"]) or store_ref),
                    "platform": platform,
                    "domain": domain,
                }
            )
        return stores

    async def _fetch_shopify_profiles(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Call the Shopify-specific delivery profile API and return a dict
        keyed by storeId, each value being the raw profiles list.

        调用 Shopify 专用 delivery profile API，返回按 storeId 分组的原始 profiles。
        """
        try:
            payload = await self._call(
                self._product_handler,
                "dsers_get_shopify_shipping_profiles",
                {},
            )
            data = payload.get("data")
            if not isinstance(data, list):
                return {}
            return {
                str(entry.get("storeId") or ""): entry.get("profiles") or []
                for entry in data
                if entry.get("storeId")
            }
        except Exception:
            return {}

    async def _enrich_shopify_profiles(self, stores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        For each Shopify store, attach a human-readable ``shipping_profiles``
        list so the caller can present available profiles to the user.

        为每个 Shopify 店铺附加人类可读的 shipping_profiles 列表，
        供调用方展示给用户选择。
        """
        has_shopify = any(
            ".myshopify.com" in (s.get("domain") or "") or str(s.get("platform") or "").lower() == "shopify"
            for s in stores
        )
        if not has_shopify:
            return stores

        profiles_by_store = await self._fetch_shopify_profiles()
        if not profiles_by_store:
            return stores

        enriched = []
        for s in stores:
            is_shopify = ".myshopify.com" in (s.get("domain") or "") or str(s.get("platform") or "").lower() == "shopify"
            if not is_shopify:
                enriched.append(s)
                continue
            raw_profiles = profiles_by_store.get(s["store_ref"], [])
            readable: List[Dict[str, Any]] = []
            for p in raw_profiles:
                groups = p.get("profileGroups") or []
                first_group = groups[0] if groups else {}
                readable.append({
                    "name": p.get("name", ""),
                    "is_default": bool(p.get("isChecked")),
                    "countries": int(first_group.get("countryCount") or 0),
                    "rate": first_group.get("rate", ""),
                    "currency": first_group.get("currency", ""),
                })
            enriched.append({**s, "shipping_profiles": readable})
        return enriched

    async def _resolve_store(self, target_store: Optional[str]) -> Dict[str, Any]:
        stores = await self._list_stores()
        if not stores:
            raise RuntimeError("The private provider could not find any linked stores.")
        if not target_store:
            if len(stores) == 1:
                return stores[0]
            raise RuntimeError("Multiple stores are available. Please provide target_store.")

        target = str(target_store).strip().lower()
        for store in stores:
            if store["store_ref"].lower() == target:
                return store
            if str(store.get("display_name") or "").strip().lower() == target:
                return store
        raise RuntimeError(f"Unknown target_store: {target_store}")

    def _extract_supply_product_id(self, payload: Dict[str, Any]) -> str:
        return str(
            self._find_first_value_by_keys(payload, ["supplyProductId", "productId", "itemId", "id"]) or ""
        ).strip()

    # ── URL & ID parsing / URL 和 ID 解析 ──

    def _resolve_source_identifier(self, source_url: str) -> Tuple[str, int, str]:
        """
        Extract platform kind, app ID, and product ID from a supplier URL.
        Returns ("unknown", default_app_id, "") if the URL does not match
        any known pattern.

        从供应商 URL 中提取平台类型、应用 ID 和商品 ID。
        如果 URL 不匹配任何已知模式，返回 ("unknown", 默认应用ID, "")。
        """
        source_url = source_url or ""
        match = ALIEXPRESS_ID_PATTERN.search(source_url)
        if match:
            return "aliexpress", self._aliexpress_app_id, match.group(1)
        match = ALIBABA_ID_PATTERN.search(source_url)
        if match:
            return "alibaba", self._alibaba_app_id, match.group(1)
        match = ALI1688_ID_PATTERN.search(source_url)
        if match:
            return "1688", self._alibaba_app_id, match.group(1)
        return "unknown", self._aliexpress_app_id, ""

    def _extract_import_item_id(self, payload: Dict[str, Any]) -> str:
        candidates = self._find_all_values_by_keys(payload, ["importListId", "id"])
        for value in candidates:
            text = str(value).strip()
            if text:
                return text
        return ""

    async def _recover_import_item_id(self, supply_product_id: str) -> str:
        listing = await self._call(self._product_handler, "dsers_get_import_list", {"page": 1, "pageSize": 20})
        for item in self._extract_import_items(listing):
            item_id = self._first_present(item, ["id", "importListId"])
            if not item_id:
                continue
            haystack = json.dumps(item, ensure_ascii=False)
            if supply_product_id and supply_product_id in haystack:
                return str(item_id)
        return ""

    # ── Draft normalisation & de-normalisation / 草稿标准化与反标准化 ──

    def _normalize_import_item(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Convert a raw DSers import item into the standard draft schema
        (title, description_html, images, tags, variants). Also builds a
        field_map that records which raw keys map to which standard fields,
        enabling lossless de-normalisation during commit.

        将原始 DSers 导入项转换为标准草稿 schema
        （title、description_html、images、tags、variants）。同时构建
        field_map 记录原始键到标准字段的映射，确保提交时可无损反标准化。
        """
        item = self._extract_import_item(payload)
        warnings: List[str] = []

        title_key = self._first_matching_key(item, ["title", "productTitle", "name"])
        description_key = self._first_matching_key(item, ["description", "descriptionHtml", "desc"])
        raw_tags_key = self._first_matching_key(item, ["tags", "tagList"])
        tags_key = None
        images_key, images, images_mode = self._extract_images(item)
        variants_key, variants = self._extract_variants(item)
        main_image_key = self._first_matching_key(item, ["mainImgUrl", "mainImageUrl"])
        price_edit_flag_key = self._first_matching_key(item, ["isPriceEdited"])
        min_price_key = self._first_matching_key(item, ["minPrice"])
        max_price_key = self._first_matching_key(item, ["maxPrice"])
        supply_key = self._first_matching_key(item, ["supply"])

        if not title_key:
            warnings.append("The private provider could not detect a stable title field; using an empty title fallback.")
        if not images_key:
            warnings.append("The private provider could not detect a top-level images field; image edits may be limited.")
        if not variants_key:
            warnings.append("The private provider could not detect a variants field; pricing edits may be limited.")
        if raw_tags_key:
            warnings.append("Import-list tag edits are preview-only in the current test backend because raw tag writes are rejected.")

        draft = {
            "title": str(item.get(title_key) or ""),
            "description_html": str(item.get(description_key) or ""),
            "images": images,
            "tags": list(item.get(raw_tags_key) or []) if raw_tags_key else [],
            "variants": variants,
        }
        field_map = {
            "title_key": title_key,
            "description_key": description_key,
            "tags_key": tags_key,
            "images_key": images_key,
            "images_mode": images_mode,
            "main_image_key": main_image_key,
            "raw_images": deepcopy(item.get(images_key) or []) if images_key else [],
            "variants_key": variants_key,
            "raw_variants": deepcopy(item.get(variants_key) or []) if variants_key else [],
            "price_edit_flag_key": price_edit_flag_key,
            "min_price_key": min_price_key,
            "max_price_key": max_price_key,
            "supply_key": supply_key,
            "raw_supply": deepcopy(item.get(supply_key) or {}) if supply_key else {},
            "variant_ref_key": "variant_ref",
        }
        return draft, field_map, warnings

    def _denormalize_variants(self, normalized_variants: List[Dict[str, Any]], field_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Write normalised variant values back into the original raw structure,
        preserving all extra fields the backend expects.

        将标准化的变体值写回原始的原始结构，保留后端期望的所有额外字段。
        """
        raw_variants = deepcopy(field_map.get("raw_variants") or [])
        if not raw_variants:
            return normalized_variants

        for idx, normalized in enumerate(normalized_variants):
            if idx >= len(raw_variants):
                break
            raw_variant = raw_variants[idx]
            offer_key = self._first_matching_key(raw_variant, ["sellPrice", "salePrice", "price"])
            supplier_key = self._first_matching_key(raw_variant, ["supplierPrice", "buyPrice", "cost"])
            title_key = self._first_matching_key(raw_variant, ["title", "name", "skuTitle"])
            sku_key = self._first_matching_key(raw_variant, ["sku", "sellerSku", "itemSku", "skuCode"])
            image_key = self._first_matching_key(raw_variant, ["imageUrl", "image", "imgUrl"])

            if offer_key:
                raw_variant[offer_key] = self._coerce_like(raw_variant.get(offer_key), normalized.get("offer_price"))
            if supplier_key and normalized.get("supplier_price") is not None:
                raw_variant[supplier_key] = self._coerce_like(raw_variant.get(supplier_key), normalized.get("supplier_price"))
            if title_key:
                raw_variant[title_key] = normalized.get("title")
            if sku_key:
                raw_variant[sku_key] = normalized.get("sku")
            if image_key and normalized.get("image_url"):
                raw_variant[image_key] = normalized.get("image_url")
        return raw_variants

    def _denormalize_supply(self, normalized_variants: List[Dict[str, Any]], field_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write normalised prices back into the 'supply' dict (keyed by variant_ref).
        DSers keeps a parallel price structure under 'supply' alongside 'variants'.

        将标准化价格写回 'supply' 字典（以 variant_ref 为键）。
        DSers 在 'variants' 之外还维护了一个平行的 'supply' 价格结构。
        """
        raw_supply = deepcopy(field_map.get("raw_supply") or {})
        if not isinstance(raw_supply, dict):
            return {}

        variants_by_ref = {
            str(item.get(field_map.get("variant_ref_key") or "variant_ref")): item
            for item in normalized_variants
            if item.get(field_map.get("variant_ref_key") or "variant_ref")
        }
        for supply_ref, raw_entry in raw_supply.items():
            if not isinstance(raw_entry, dict):
                continue
            normalized = variants_by_ref.get(str(supply_ref))
            if not normalized:
                continue
            offer_key = self._first_matching_key(raw_entry, ["sellPrice", "salePrice", "price"])
            supplier_key = self._first_matching_key(raw_entry, ["supplierPrice", "buyPrice", "cost"])
            compare_key = self._first_matching_key(raw_entry, ["compareAtPrice"])
            if offer_key:
                raw_entry[offer_key] = self._coerce_like(raw_entry.get(offer_key), normalized.get("offer_price"))
            if supplier_key and normalized.get("supplier_price") is not None:
                raw_entry[supplier_key] = self._coerce_like(raw_entry.get(supplier_key), normalized.get("supplier_price"))
            if compare_key and normalized.get("offer_price") is not None:
                raw_entry[compare_key] = self._coerce_like(raw_entry.get(compare_key), normalized.get("offer_price"))
        return raw_supply

    def _denormalize_images(self, normalized_images: List[str], field_map: Dict[str, Any]) -> List[Any]:
        raw_images = deepcopy(field_map.get("raw_images") or [])
        if not raw_images:
            return normalized_images
        if field_map.get("images_mode") == "string_list":
            return [str(item) for item in normalized_images if item]
        if field_map.get("images_mode") != "dict_list":
            return raw_images

        result = []
        for idx, url in enumerate(normalized_images):
            if not url:
                continue
            template = raw_images[idx] if idx < len(raw_images) and isinstance(raw_images[idx], dict) else {}
            entry = dict(template)
            image_key = self._first_matching_key(entry, ["url", "imageUrl", "src", "originUrl", "imgUrl"])
            if image_key:
                entry[image_key] = url
            elif entry:
                first_key = next(iter(entry))
                entry[first_key] = url
            else:
                entry = {"url": url}
            result.append(entry)
        return result

    def _extract_images(self, item: Dict[str, Any]) -> Tuple[Optional[str], List[str], str]:
        for key in ["medias", "images", "productImages", "imageList", "mainImages"]:
            value = item.get(key)
            if not isinstance(value, list):
                continue
            if not value:
                return key, [], "string_list"
            if all(isinstance(entry, str) for entry in value):
                return key, [entry for entry in value if entry], "string_list"

            urls = []
            for entry in value:
                if isinstance(entry, dict):
                    url = self._first_present(entry, ["url", "imageUrl", "src", "originUrl", "imgUrl"])
                    if url:
                        urls.append(str(url))
            if urls:
                return key, urls, "dict_list"
        return None, self._variant_images(item), "unknown"

    def _compute_price_bounds(self, normalized_variants: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        prices = [self._as_float(item.get("offer_price")) for item in normalized_variants]
        prices = [price for price in prices if price is not None]
        if not prices:
            return None, None
        return self._format_scalar(min(prices)), self._format_scalar(max(prices))

    def _variant_images(self, item: Dict[str, Any]) -> List[str]:
        _, variants = self._extract_variants(item)
        seen = []
        for variant in variants:
            url = variant.get("image_url")
            if url and url not in seen:
                seen.append(url)
        return seen

    def _extract_variants(self, item: Dict[str, Any]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        for key in ["variants", "skuList", "variantList", "productSkuList"]:
            value = item.get(key)
            if not isinstance(value, list):
                continue
            normalized = []
            for idx, raw in enumerate(value):
                if not isinstance(raw, dict):
                    continue
                variant_ref = self._first_present(raw, ["id", "variantId", "skuId", "sellerSku"]) or f"variant-{idx}"
                normalized.append(
                    {
                        "variant_ref": str(variant_ref),
                        "title": str(self._first_present(raw, ["title", "name", "skuTitle", "skuAttr"]) or f"Variant {idx + 1}"),
                        "supplier_price": self._as_float(self._first_present(raw, ["supplierPrice", "buyPrice", "cost", "price"])),
                        "offer_price": self._as_float(self._first_present(raw, ["sellPrice", "salePrice", "price"])),
                        "sku": str(self._first_present(raw, ["sku", "sellerSku", "itemSku", "skuCode"]) or ""),
                        "image_url": str(self._first_present(raw, ["imageUrl", "image", "imgUrl"]) or ""),
                    }
                )
            return key, normalized
        return None, []

    def _extract_import_item(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data", payload)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        if isinstance(payload, dict):
            return payload
        raise RuntimeError("The private provider could not normalize the imported draft payload.")

    def _extract_import_items(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = self._find_list_candidates(payload)
        scored = []
        for key, items in candidates:
            if not items:
                continue
            score = 0
            if "import" in key.lower():
                score += 2
            sample = items[0]
            if isinstance(sample, dict) and self._first_present(sample, ["id", "importListId"]):
                score += 1
            scored.append((score, items))
        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _extract_store_dicts(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = self._find_list_candidates(payload)
        scored = []
        for key, items in candidates:
            if not items:
                continue
            score = 0
            if "store" in key.lower():
                score += 2
            sample = items[0]
            if isinstance(sample, dict) and self._first_present(sample, ["storeId", "id"]):
                score += 1
            scored.append((score, items))
        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    # ── Push status parsing / 推送状态解析 ──

    def _extract_push_state(self, payload: Dict[str, Any]) -> str:
        """
        Map DSers numeric push status codes to human-readable strings.
        DSers uses: 0/1 = requested, 4 = failed, 5 = completed.

        将 DSers 数字推送状态码映射为可读字符串。
        DSers 使用：0/1 = 已请求，4 = 失败，5 = 完成。
        """
        state = self._find_first_value_by_keys(payload, ["status", "state", "result"])
        mapped_states = {
            0: "requested",
            "0": "requested",
            1: "requested",
            "1": "requested",
            4: "failed",
            "4": "failed",
            5: "completed",
            "5": "completed",
        }
        if state in mapped_states:
            return mapped_states[state]
        return str(state or "requested")

    def _extract_push_error(self, payload: Dict[str, Any]) -> str:
        message = self._find_first_value_by_keys(payload, ["errmsg", "message", "detail", "error"])
        reason = self._find_first_value_by_keys(payload, ["reason"])
        pieces = [str(part).strip() for part in (message, reason) if part not in (None, "")]
        return " | ".join(dict.fromkeys(pieces))

    # ── Generic JSON traversal helpers / 通用 JSON 遍历辅助方法 ──
    # These helpers navigate DSers responses whose structure may vary
    # between API versions, making the adapter resilient to schema drift.
    # 这些辅助方法用于遍历 DSers 响应（其结构在不同 API 版本间可能不同），
    # 使适配器能抵御 schema 漂移。

    def _find_list_candidates(self, node: Any, prefix: str = "root") -> List[Tuple[str, List[Dict[str, Any]]]]:
        results: List[Tuple[str, List[Dict[str, Any]]]] = []
        if isinstance(node, dict):
            for key, value in node.items():
                child_prefix = f"{prefix}.{key}"
                if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                    results.append((child_prefix, value))
                results.extend(self._find_list_candidates(value, child_prefix))
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                results.extend(self._find_list_candidates(value, f"{prefix}[{idx}]"))
        return results

    def _find_first_value_by_keys(self, node: Any, keys: List[str]) -> Any:
        if isinstance(node, dict):
            for key in keys:
                if key in node and node[key] not in (None, ""):
                    return node[key]
            for value in node.values():
                found = self._find_first_value_by_keys(value, keys)
                if found not in (None, ""):
                    return found
        elif isinstance(node, list):
            for value in node:
                found = self._find_first_value_by_keys(value, keys)
                if found not in (None, ""):
                    return found
        return None

    def _find_all_values_by_keys(self, node: Any, keys: List[str]) -> List[Any]:
        found: List[Any] = []
        if isinstance(node, dict):
            for key in keys:
                if key in node and node[key] not in (None, ""):
                    found.append(node[key])
            for value in node.values():
                found.extend(self._find_all_values_by_keys(value, keys))
        elif isinstance(node, list):
            for value in node:
                found.extend(self._find_all_values_by_keys(value, keys))
        return found

    def _first_matching_key(self, node: Dict[str, Any], keys: List[str]) -> Optional[str]:
        for key in keys:
            if key in node:
                return key
        return None

    def _first_present(self, node: Dict[str, Any], keys: List[str]) -> Any:
        for key in keys:
            value = node.get(key)
            if value not in (None, ""):
                return value
        return None

    def _as_float(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ── Type coercion / 类型强制转换 ──

    def _coerce_like(self, original: Any, value: Any) -> Any:
        """
        Coerce a value to match the type of the original (str vs numeric).
        Prevents type mismatches when writing prices back to the raw payload.

        将值强制转换为与原始值相同的类型（字符串 vs 数值）。
        防止将价格写回原始 payload 时发生类型不匹配。
        """
        if value is None:
            return value
        if isinstance(original, str):
            return self._format_scalar(value)
        return value

    def _format_scalar(self, value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if number.is_integer():
            return str(int(number))
        text = f"{number:.2f}"
        return text.rstrip("0").rstrip(".")


def build_provider() -> ImportProvider:
    return PrivateDsersProvider()
