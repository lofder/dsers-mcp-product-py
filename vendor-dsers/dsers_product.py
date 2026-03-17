"""DSers Product module — MCP tools for dsers-product-bff API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp.types import TextContent, Tool

if TYPE_CHECKING:
    from dsers_mcp_base.client import DSersClient


def register(app: Any, client: "DSersClient") -> tuple[list[Tool], Any]:
    """Register all product-related MCP tools. Returns (TOOLS, handle)."""

    TOOLS = [
        # --- Import List ---
        Tool(
            name="dsers_get_import_list",
            description="Get paginated import list. Filter by keyword, storeIds, tagIds, isPushed, shipTo, cost range, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyWord": {"type": "string", "description": "Search keyword"},
                    "storeIds": {"type": "string", "description": "Comma-separated store IDs"},
                    "tagIds": {"type": "string", "description": "Comma-separated tag IDs"},
                    "page": {"type": "integer", "description": "Page number"},
                    "pageSize": {"type": "integer", "description": "Items per page"},
                    "isPushed": {"type": "boolean", "description": "Filter by push status"},
                    "shipTo": {"type": "string", "description": "Ship-to country code"},
                    "orderBy": {"type": "string", "description": "Sort field"},
                    "cursor": {"type": "string", "description": "Cursor for pagination"},
                    "costMin": {"type": "number", "description": "Minimum cost filter"},
                    "costMax": {"type": "number", "description": "Maximum cost filter"},
                    "shipFrom": {"type": "string", "description": "Ship-from country code"},
                },
                "required": [],
            },
        ),
        Tool(
            name="dsers_get_import_list_item",
            description="Get a single import list item by ID.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Import list item ID"}},
                "required": ["id"],
            },
        ),
        Tool(
            name="dsers_import_by_product_id",
            description="Import a product by supplier product ID. Requires supplyProductId, supplyAppId, country.",
            inputSchema={
                "type": "object",
                "properties": {
                    "supplyProductId": {"type": "string", "description": "Supplier product ID"},
                    "supplyAppId": {"type": "integer", "description": "Supplier app ID (e.g. AliExpress)"},
                    "country": {"type": "string", "description": "Target country code (e.g. US)"},
                    "language": {"type": "array", "items": {"type": "string"}, "description": "Optional language codes"},
                },
                "required": ["supplyProductId", "supplyAppId", "country"],
            },
        ),
        Tool(
            name="dsers_import_by_product_id_batch",
            description="Batch import products by supplier product IDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "supplyProductIds": {"type": "array", "items": {"type": "string"}, "description": "Supplier product IDs"},
                    "supplyAppId": {"type": "integer", "description": "Supplier app ID"},
                    "country": {"type": "string", "description": "Target country code"},
                    "isBackError": {"type": "integer", "description": "0 or 1, whether to return errors"},
                },
                "required": ["supplyProductIds", "supplyAppId", "country"],
            },
        ),
        Tool(
            name="dsers_update_import_list_item",
            description=(
                "Update an import list item (title, description, variants, etc.). "
                "Automatically fetches the full product object first, merges your changes, "
                "then sends the complete object to the API. Only pass the fields you want to change."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Import list item ID (required)"},
                    "title": {"type": "string", "description": "New product title"},
                    "description": {"type": "string", "description": "New product description (HTML supported)"},
                    "variants": {"type": "array", "description": "Updated variant data array"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Product tags"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="dsers_delete_import_list",
            description="Delete import list items by comma-separated IDs.",
            inputSchema={
                "type": "object",
                "properties": {"ids": {"type": "string", "description": "Comma-separated import list IDs"}},
                "required": ["ids"],
            },
        ),
        Tool(
            name="dsers_push_to_store",
            description="Push import list items to stores. Accepts PushProductInfo fields and wraps them in the API's required data envelope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "Optional raw PushProductRequest.data payload. When provided, it is sent directly after ID normalization."},
                    "importListIds": {"type": "array", "items": {"type": "string"}, "description": "Import list IDs to push"},
                    "storeId": {"type": "string", "description": "Single-store convenience alias. Converted to storeIds=[storeId]."},
                    "storeIds": {"type": "array", "items": {"type": "string"}, "description": "Target store ID list"},
                    "withPriceRule": {"type": "boolean", "description": "Whether to use DSers pricing rule"},
                    "visible": {"type": "boolean", "description": "Whether the product should be visible in the online store"},
                    "inventoryPolicy": {"type": "boolean", "description": "Whether to continue selling when inventory is zero"},
                    "onlyPushSpecifications": {"type": "boolean", "description": "Whether description should only push specifications"},
                    "pushStatus": {"type": "string", "enum": ["ACTIVE", "DRAFT"], "description": "Pushed product status"},
                    "pushProducts": {"type": "array", "items": {"type": "object"}, "description": "Per-product language push settings"},
                    "stores": {"type": "array", "items": {"type": "object"}, "description": "Target stores and market selections"},
                    "myProductSyncSetting": {"type": "object", "description": "Sync settings such as stock and price auto-update"},
                    "skus": {"type": "array", "items": {"type": "string"}, "description": "Optional partial SKU push list"},
                    "isPushAllImage": {"type": "boolean", "description": "Whether to push all images"},
                    "saleChannels": {"type": "array", "items": {"type": "string"}, "description": "Sales channel list"},
                    "logistics": {"type": "array", "items": {"type": "object"}, "description": "Manual logistics selections"},
                    "pricingRuleImportListIds": {"type": "array", "items": {"type": "object"}, "description": "Import/store pairs that should apply pricing rule"},
                    "storeLanguageList": {"type": "array", "items": {"type": "object"}, "description": "Store language settings"},
                    "storeShippingProfile": {"type": "array", "items": {"type": "object"}, "description": "Store delivery profile bindings. Each item: {storeId, locationId (DeliveryLocationGroup GID), profileId (DeliveryProfile GID)}."},
                    "pushOptions": {"type": "object", "description": "Legacy compatibility object. Known fields are mapped into the modern PushProductInfo schema."},
                    "storeParams": {"type": "array", "items": {"type": "object"}, "description": "Legacy compatibility array. Store IDs and known options are mapped into the modern PushProductInfo schema."},
                },
                "required": [],
            },
        ),
        Tool(
            name="dsers_push_before_check",
            description="Check whether import list items can be pushed to stores before submitting the async push job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "importListIds": {"type": "array", "items": {"type": "string"}, "description": "Import list IDs to check"},
                    "storeIds": {"type": "array", "items": {"type": "string"}, "description": "Target store IDs"},
                    "onlyPushSpecifications": {"type": "boolean"},
                    "importListIdSkus": {"type": "array", "items": {"type": "object"}, "description": "Optional SKU subset selections"},
                    "storeIdsLanguage": {"type": "array", "items": {"type": "object"}, "description": "Optional store-language mappings"},
                    "pushOnlineStore": {"type": "boolean", "description": "Whether the also publish to online store option is enabled"},
                    "isPushAllImage": {"type": "boolean"},
                },
                "required": ["importListIds", "storeIds"],
            },
        ),
        Tool(
            name="dsers_get_push_price",
            description="Preview push prices for import list items across the selected stores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "importListIds": {"type": "array", "items": {"type": "string"}, "description": "Import list IDs to price"},
                    "storeIds": {"type": "array", "items": {"type": "string"}, "description": "Target store IDs"},
                    "withPriceRule": {"type": "boolean"},
                    "shipCost": {"type": "string"},
                    "shipTo": {"type": "string"},
                    "logisticInfos": {"type": "array", "items": {"type": "object"}, "description": "Manual logistics selections"},
                    "pricingRuleImportListIds": {"type": "array", "items": {"type": "object"}, "description": "Import/store pairs that should apply pricing rule"},
                    "shipFrom": {"type": "string"},
                },
                "required": ["importListIds", "storeIds"],
            },
        ),
        Tool(
            name="dsers_get_push_logistics",
            description="Query available logistics options for import list items across the selected stores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "importListIds": {"type": "array", "items": {"type": "string"}, "description": "Import list IDs"},
                    "storeIds": {"type": "array", "items": {"type": "string"}, "description": "Target store IDs"},
                },
                "required": ["importListIds", "storeIds"],
            },
        ),
        Tool(
            name="dsers_get_push_status",
            description="Get push status by event ID.",
            inputSchema={
                "type": "object",
                "properties": {"event_id": {"type": "string", "description": "Push event ID"}},
                "required": ["event_id"],
            },
        ),
        Tool(
            name="dsers_get_store_shipping_profile",
            description="Get store delivery profile bindings (locationId and profileId) needed for product push.",
            inputSchema={
                "type": "object",
                "properties": {
                    "storeId": {"type": "string", "description": "Optional store ID to filter results"},
                },
                "required": [],
            },
        ),
        Tool(
            name="dsers_get_shopify_shipping_profiles",
            description="Get Shopify delivery profiles for all linked Shopify stores. Returns profile GIDs and location group GIDs needed for the storeShippingProfile push field. The profile with isChecked=true is the active one.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="dsers_list_import_tags",
            description="List all import list tags.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="dsers_create_import_tag",
            description="Create a new import list tag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tag name"},
                    "color": {"type": "string", "description": "Optional hex color"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="dsers_delete_import_tag",
            description="Delete import list tags by comma-separated IDs.",
            inputSchema={
                "type": "object",
                "properties": {"ids": {"type": "string", "description": "Comma-separated tag IDs"}},
                "required": ["ids"],
            },
        ),
        # --- My Products ---
        Tool(
            name="dsers_get_my_products",
            description="Get my products list. Requires storeId. Filter by keyword, mappingType, supplyType, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "storeId": {"type": "integer", "description": "Store ID (required)"},
                    "keyWord": {"type": "string"},
                    "mappingType": {"type": "string"},
                    "page": {"type": "integer"},
                    "pageSize": {"type": "integer"},
                    "cursor": {"type": "string"},
                    "supplyType": {"type": "string"},
                    "productType": {"type": "string"},
                    "supplyProductStatus": {"type": "string"},
                    "isUnable": {"type": "boolean"},
                    "isSellerDelete": {"type": "boolean"},
                    "costMin": {"type": "number"},
                    "costMax": {"type": "number"},
                    "shipTo": {"type": "string"},
                    "shipFrom": {"type": "string"},
                    "orderBy": {"type": "string"},
                },
                "required": ["storeId"],
            },
        ),
        Tool(
            name="dsers_hide_my_product",
            description="Hide my products. Pass dsersProductIds (comma-sep) and storeId.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dsersProductIds": {"type": "string", "description": "Comma-separated DSers product IDs"},
                    "storeId": {"type": "integer", "description": "Store ID"},
                },
                "required": ["dsersProductIds", "storeId"],
            },
        ),
        Tool(
            name="dsers_delete_my_product",
            description="Delete my products. Pass dsersProductIds (comma-sep), storeId, and optionally deleteSeller.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dsersProductIds": {"type": "string", "description": "Comma-separated DSers product IDs"},
                    "storeId": {"type": "integer", "description": "Store ID"},
                    "deleteSeller": {"type": "boolean", "description": "Also delete from seller store"},
                },
                "required": ["dsersProductIds", "storeId"],
            },
        ),
        # --- Mapping ---
        Tool(
            name="dsers_get_mapping",
            description="Get variant mapping for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {"dsers_product_id": {"type": "string", "description": "DSers product ID"}},
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_create_variant_mapping",
            description="Create or update variant mapping for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dsers_product_id": {"type": "string", "description": "DSers product ID"},
                    "mapping": {"type": "object", "description": "Variant mapping data"},
                },
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_delete_mapping",
            description="Delete mapping for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {"dsers_product_id": {"type": "string", "description": "DSers product ID"}},
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_get_mapped_suppliers",
            description="Get mapped suppliers for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {"dsers_product_id": {"type": "string", "description": "DSers product ID"}},
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_get_mapping_pool",
            description="Get mapping pool for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dsers_product_id": {"type": "string", "description": "DSers product ID"},
                    "mappingType": {"type": "string", "description": "Mapping type filter"},
                },
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_import_mapping_pool",
            description="Add supply product to mapping pool for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dsers_product_id": {"type": "string", "description": "DSers product ID"},
                    "supplyProduct": {"type": "object", "description": "Supply product info to add"},
                },
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_check_mapping_status",
            description="Check mapping process status for a DSers product.",
            inputSchema={
                "type": "object",
                "properties": {"dsers_product_id": {"type": "string", "description": "DSers product ID"}},
                "required": ["dsers_product_id"],
            },
        ),
        Tool(
            name="dsers_search_mapping_products",
            description="Search mapping list products by keyword and store.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "storeId": {"type": "string"},
                    "page": {"type": "integer"},
                    "pageSize": {"type": "integer"},
                },
                "required": [],
            },
        ),
        # --- Product Pool ---
        Tool(
            name="dsers_get_pool_product_detail",
            description="Get product pool product detail by productId, appId, shipTo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "productId": {"type": "string", "description": "Product ID"},
                    "appId": {"type": "integer", "description": "App ID"},
                    "shipTo": {"type": "string", "description": "Ship-to country code"},
                },
                "required": ["productId", "appId", "shipTo"],
            },
        ),
        Tool(
            name="dsers_get_pool_product_logistics",
            description="Get product pool product logistics info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "productId": {"type": "string"},
                    "appId": {"type": "integer"},
                    "shipTo": {"type": "string"},
                    "country": {"type": "string"},
                },
                "required": ["productId", "appId", "shipTo"],
            },
        ),
        Tool(
            name="dsers_search_product_pool",
            description="Search product pool by keyword and category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "category": {"type": "string"},
                    "page": {"type": "integer"},
                    "pageSize": {"type": "integer"},
                },
                "required": [],
            },
        ),
        # --- Find Suppliers ---
        Tool(
            name="dsers_find_suppliers",
            description="Find suppliers/products by keyword, shipTo, price range, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "supplyAppId": {"type": "integer", "description": "Supplier app ID"},
                    "keyword": {"type": "string"},
                    "shipTo": {"type": "string"},
                    "shipFrom": {"type": "string"},
                    "minPrice": {"type": "number"},
                    "maxPrice": {"type": "number"},
                    "sort": {"type": "string"},
                    "limit": {"type": "integer"},
                    "searchAfter": {"type": "string"},
                    "categoryId": {"type": "string"},
                    "deliveryTime": {"type": "string"},
                    "language": {"type": "string"},
                    "agentType": {"type": "string"},
                },
                "required": ["supplyAppId"],
            },
        ),
        Tool(
            name="dsers_find_suppliers_by_image",
            description="Find suppliers by image URL (reverse image search).",
            inputSchema={
                "type": "object",
                "properties": {
                    "imgUrl": {"type": "string", "description": "Image URL"},
                    "shipFrom": {"type": "string"},
                    "shipTo": {"type": "string"},
                    "appId": {"type": "integer", "description": "Supplier app ID"},
                },
                "required": ["imgUrl"],
            },
        ),
        Tool(
            name="dsers_get_supplier_categories",
            description="Get supplier categories for an app.",
            inputSchema={
                "type": "object",
                "properties": {"supplierAppId": {"type": "integer", "description": "Supplier app ID"}},
                "required": ["supplierAppId"],
            },
        ),
        Tool(
            name="dsers_get_ship_from_list",
            description="Get ship-from list for a supplier app.",
            inputSchema={
                "type": "object",
                "properties": {"supplyAppId": {"type": "integer", "description": "Supplier app ID"}},
                "required": ["supplyAppId"],
            },
        ),
        # --- URL Parsing ---
        Tool(
            name="dsers_parse_product_url",
            description="Parse a supplier product URL to extract product info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Product URL to parse"},
                    "appId": {"type": "integer", "description": "Supplier app ID"},
                },
                "required": ["url", "appId"],
            },
        ),
    ]

    def reply(data: Any) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

    def _params(args: dict[str, Any], *keys: str) -> dict[str, Any]:
        """Build params dict with only non-None values for the given keys."""
        return {k: args.get(k) for k in keys if args.get(k) is not None}

    def _clean_none(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _clean_none(v) for k, v in value.items() if v is not None}
        if isinstance(value, list):
            return [_clean_none(v) for v in value if v is not None]
        return value

    def _coerce_int_id(value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                try:
                    return int(text)
                except ValueError:
                    return value
        return value

    def _merge_legacy_push_settings(target: dict[str, Any], source: Any) -> None:
        if not isinstance(source, dict):
            return

        def set_if_missing(key: str, value: Any) -> None:
            if value is not None and target.get(key) is None:
                target[key] = value

        visible = None
        for key in ("visible", "publishToOnlineStore", "pushOnlineStore", "alsoPublishToOnlineStore", "publishOnlineStore"):
            if key in source:
                visible = bool(source.get(key))
                break
        set_if_missing("visible", visible)

        inventory_policy = None
        for key in ("inventoryPolicy", "outofStockSelling"):
            if key in source:
                inventory_policy = bool(source.get(key))
                break
        set_if_missing("inventoryPolicy", inventory_policy)

        only_push_specifications = None
        if "onlyPushSpecifications" in source:
            only_push_specifications = bool(source.get("onlyPushSpecifications"))
        set_if_missing("onlyPushSpecifications", only_push_specifications)

        is_push_all_image = None
        for key in ("isPushAllImage", "isPushAllImages", "pushAllImages"):
            if key in source:
                is_push_all_image = bool(source.get(key))
                break
        set_if_missing("isPushAllImage", is_push_all_image)

        with_price_rule = None
        for key in ("withPriceRule", "applyPricingRule", "pricing", "pricingRuleApplied", "usePricingRule"):
            if key in source:
                with_price_rule = bool(source.get(key))
                break
        set_if_missing("withPriceRule", with_price_rule)

        sale_channels = None
        for key in ("saleChannels", "salesChannels", "publishChannels"):
            if source.get(key) is not None:
                sale_channels = source.get(key)
                break
        set_if_missing("saleChannels", sale_channels)

        push_status = source.get("pushStatus")
        if push_status is None and source.get("pushAsDraft") is not None:
            push_as_draft = str(source.get("pushAsDraft") or "").strip().upper()
            if push_as_draft == "ACTIVE":
                push_status = "ACTIVE"
            elif push_as_draft == "DRAFT":
                push_status = "DRAFT"
            elif push_as_draft == "TRUE":
                push_status = "ACTIVE"
            elif push_as_draft == "FALSE":
                push_status = "DRAFT"
        if isinstance(push_status, str):
            normalized_status = push_status.strip().upper()
            if normalized_status in {"ACTIVE", "DRAFT"}:
                set_if_missing("pushStatus", normalized_status)

        sync = target.get("myProductSyncSetting")
        if not isinstance(sync, dict):
            sync = {}
        sync_changed = False
        for source_key, target_key in (
            ("autoUpdateStock", "autoUpdateStock"),
            ("autoInventoryUpdate", "autoUpdateStock"),
            ("automaticInventoryUpdate", "autoUpdateStock"),
            ("autoUpdatePrice", "autoUpdatePrice"),
            ("automaticPriceUpdate", "autoUpdatePrice"),
            ("handleUpdatePrice", "handleUpdatePrice"),
        ):
            if source.get(source_key) is not None and sync.get(target_key) is None:
                sync[target_key] = bool(source.get(source_key))
                sync_changed = True
        if sync_changed and target.get("myProductSyncSetting") is None:
            target["myProductSyncSetting"] = sync
        elif sync_changed:
            target["myProductSyncSetting"] = sync

    def _normalize_push_product_payload(arguments: dict[str, Any]) -> dict[str, Any]:
        raw_data = arguments.get("data")
        if isinstance(raw_data, dict):
            payload = {k: v for k, v in raw_data.items() if v is not None}
        else:
            payload = {
                k: v for k, v in arguments.items()
                if v is not None and k not in {"data", "storeId", "pushOptions", "storeParams"}
            }

        if payload.get("storeIds") is None and arguments.get("storeId") is not None:
            payload["storeIds"] = [arguments.get("storeId")]

        store_params = arguments.get("storeParams")
        if payload.get("storeIds") is None and isinstance(store_params, list):
            store_ids = [
                item.get("storeId")
                for item in store_params
                if isinstance(item, dict) and item.get("storeId") is not None
            ]
            if store_ids:
                payload["storeIds"] = store_ids

        _merge_legacy_push_settings(payload, arguments.get("pushOptions"))
        if isinstance(store_params, list) and store_params:
            _merge_legacy_push_settings(payload, store_params[0])

        if isinstance(payload.get("importListIds"), list):
            payload["importListIds"] = [_coerce_int_id(item) for item in payload["importListIds"]]
        if isinstance(payload.get("storeIds"), list):
            payload["storeIds"] = [_coerce_int_id(item) for item in payload["storeIds"]]
        if isinstance(payload.get("pushProducts"), list):
            for item in payload["pushProducts"]:
                if isinstance(item, dict) and item.get("importListId") is not None:
                    item["importListId"] = _coerce_int_id(item["importListId"])
        if isinstance(payload.get("stores"), list):
            for item in payload["stores"]:
                if isinstance(item, dict) and item.get("storeId") is not None:
                    item["storeId"] = _coerce_int_id(item["storeId"])
        if isinstance(payload.get("pricingRuleImportListIds"), list):
            for item in payload["pricingRuleImportListIds"]:
                if isinstance(item, dict):
                    if item.get("importListId") is not None:
                        item["importListId"] = _coerce_int_id(item["importListId"])
                    if item.get("storeId") is not None:
                        item["storeId"] = _coerce_int_id(item["storeId"])
        if isinstance(payload.get("storeLanguageList"), list):
            for item in payload["storeLanguageList"]:
                if isinstance(item, dict) and item.get("storeId") is not None:
                    item["storeId"] = _coerce_int_id(item["storeId"])
        if isinstance(payload.get("logistics"), list):
            for item in payload["logistics"]:
                if isinstance(item, dict):
                    if item.get("importListId") is not None:
                        item["importListId"] = _coerce_int_id(item["importListId"])
                    if item.get("storeId") is not None:
                        item["storeId"] = _coerce_int_id(item["storeId"])
        if isinstance(payload.get("storeShippingProfile"), list):
            for item in payload["storeShippingProfile"]:
                if isinstance(item, dict) and item.get("storeId") is not None:
                    item["storeId"] = _coerce_int_id(item["storeId"])

        return _clean_none(payload)

    async def handle(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            # --- Import List ---
            if name == "dsers_get_import_list":
                params = _params(
                    arguments,
                    "keyWord", "storeIds", "tagIds", "page", "pageSize", "isPushed",
                    "shipTo", "orderBy", "cursor", "costMin", "costMax", "shipFrom",
                )
                data = await client.get("/dsers-product-bff/import-list", **params)
                return reply(data)

            if name == "dsers_get_import_list_item":
                id_ = arguments.get("id")
                if not id_:
                    return reply({"error": "id is required"})
                data = await client.get(f"/dsers-product-bff/import-list/{id_}")
                return reply(data)

            if name == "dsers_import_by_product_id":
                body = {
                    "supplyProductId": arguments.get("supplyProductId"),
                    "supplyAppId": arguments.get("supplyAppId"),
                    "country": arguments.get("country"),
                }
                if body["supplyProductId"] is None or body["supplyAppId"] is None or body["country"] is None:
                    return reply({"error": "supplyProductId, supplyAppId, and country are required"})
                if "language" in arguments and arguments["language"] is not None:
                    body["language"] = arguments["language"]
                data = await client.post("/dsers-product-bff/import-list/product-id", json=body)
                return reply(data)

            if name == "dsers_import_by_product_id_batch":
                body = {
                    "supplyProductIds": arguments.get("supplyProductIds"),
                    "supplyAppId": arguments.get("supplyAppId"),
                    "country": arguments.get("country"),
                }
                if body["supplyProductIds"] is None or body["supplyAppId"] is None or body["country"] is None:
                    return reply({"error": "supplyProductIds, supplyAppId, and country are required"})
                if arguments.get("isBackError") is not None:
                    body["isBackError"] = arguments["isBackError"]
                data = await client.post("/dsers-product-bff/import-list/product-id-batch", json=body)
                return reply(data)

            if name == "dsers_update_import_list_item":
                id_ = arguments.get("id")
                if not id_:
                    return reply({"error": "id is required"})
                existing = await client.get(f"/dsers-product-bff/import-list/{id_}")
                product = existing.get("data", existing)
                if isinstance(product, dict):
                    updates = {k: v for k, v in arguments.items() if k != "id" and v is not None}
                    product.update(updates)
                else:
                    product = {k: v for k, v in arguments.items() if k != "id" and v is not None}
                data = await client.put(f"/dsers-product-bff/import-list/{id_}", json=product)
                return reply({"ok": True, "updated_fields": list(updates.keys()), "api_response": data})

            if name == "dsers_delete_import_list":
                ids = arguments.get("ids")
                if not ids:
                    return reply({"error": "ids is required"})
                data = await client.delete(f"/dsers-product-bff/import-list/{ids}")
                return reply(data)

            if name == "dsers_push_to_store":
                body = _normalize_push_product_payload(arguments)
                if not body.get("importListIds") or not body.get("storeIds"):
                    return reply({"error": "importListIds and storeIds (or storeId) are required"})
                data = await client.post("/dsers-product-bff/import-list/push", json={"data": body})
                return reply(data)

            if name == "dsers_push_before_check":
                body = _clean_none({
                    "importListIds": [_coerce_int_id(item) for item in arguments.get("importListIds", [])],
                    "storeIds": [_coerce_int_id(item) for item in arguments.get("storeIds", [])],
                    "onlyPushSpecifications": arguments.get("onlyPushSpecifications"),
                    "importListIdSkus": arguments.get("importListIdSkus"),
                    "storeIdsLanguage": arguments.get("storeIdsLanguage"),
                    "pushOnlineStore": arguments.get("pushOnlineStore"),
                    "isPushAllImage": arguments.get("isPushAllImage"),
                })
                if not body.get("importListIds") or not body.get("storeIds"):
                    return reply({"error": "importListIds and storeIds are required"})
                data = await client.post("/dsers-product-bff/import-list/push-before/check", json=body)
                return reply(data)

            if name == "dsers_get_push_price":
                body = _clean_none({
                    "importListIds": [_coerce_int_id(item) for item in arguments.get("importListIds", [])],
                    "storeIds": [_coerce_int_id(item) for item in arguments.get("storeIds", [])],
                    "withPriceRule": arguments.get("withPriceRule"),
                    "shipCost": arguments.get("shipCost"),
                    "shipTo": arguments.get("shipTo"),
                    "logisticInfos": arguments.get("logisticInfos"),
                    "pricingRuleImportListIds": arguments.get("pricingRuleImportListIds"),
                    "shipFrom": arguments.get("shipFrom"),
                })
                if not body.get("importListIds") or not body.get("storeIds"):
                    return reply({"error": "importListIds and storeIds are required"})
                data = await client.post("/dsers-product-bff/import-list/push-price", json=body)
                return reply(data)

            if name == "dsers_get_push_logistics":
                body = _clean_none({
                    "importListIds": [_coerce_int_id(item) for item in arguments.get("importListIds", [])],
                    "storeIds": [_coerce_int_id(item) for item in arguments.get("storeIds", [])],
                })
                if not body.get("importListIds") or not body.get("storeIds"):
                    return reply({"error": "importListIds and storeIds are required"})
                data = await client.post("/dsers-product-bff/import-list/push-logistics", json=body)
                return reply(data)

            if name == "dsers_get_push_status":
                event_id = arguments.get("event_id")
                if not event_id:
                    return reply({"error": "event_id is required"})
                data = await client.get(f"/dsers-product-bff/import-list/push/{event_id}")
                return reply(data)

            if name == "dsers_get_store_shipping_profile":
                params = _params(arguments, "storeId")
                data = await client.get("/dsers-product-bff/import-list/push/store-shipping-profile", **params)
                return reply(data)

            if name == "dsers_get_shopify_shipping_profiles":
                data = await client.get("/dsers-product-bff/import-list/shopify/shipping-profile/get")
                return reply(data)

            if name == "dsers_list_import_tags":
                data = await client.get("/dsers-product-bff/import-list/all/tags")
                return reply(data)

            if name == "dsers_create_import_tag":
                body = {"name": arguments.get("name")}
                if not body["name"]:
                    return reply({"error": "name is required"})
                if arguments.get("color") is not None:
                    body["color"] = arguments["color"]
                data = await client.post("/dsers-product-bff/import-list/tags", json=body)
                return reply(data)

            if name == "dsers_delete_import_tag":
                ids = arguments.get("ids")
                if not ids:
                    return reply({"error": "ids is required"})
                data = await client.delete(f"/dsers-product-bff/import-list/tags/{ids}")
                return reply(data)

            # --- My Products ---
            if name == "dsers_get_my_products":
                params = _params(
                    arguments,
                    "storeId", "keyWord", "mappingType", "page", "pageSize", "cursor",
                    "supplyType", "productType", "supplyProductStatus", "isUnable",
                    "isSellerDelete", "costMin", "costMax", "shipTo", "shipFrom", "orderBy",
                )
                if not params.get("storeId"):
                    return reply({"error": "storeId is required"})
                data = await client.get("/dsers-product-bff/my-product", **params)
                return reply(data)

            if name == "dsers_hide_my_product":
                body = {
                    "dsersProductIds": arguments.get("dsersProductIds"),
                    "storeId": arguments.get("storeId"),
                }
                if not body["dsersProductIds"] or body["storeId"] is None:
                    return reply({"error": "dsersProductIds and storeId are required"})
                data = await client.put("/dsers-product-bff/my-product", json=body)
                return reply(data)

            if name == "dsers_delete_my_product":
                params = _params(arguments, "dsersProductIds", "storeId", "deleteSeller")
                if not params.get("dsersProductIds") or params.get("storeId") is None:
                    return reply({"error": "dsersProductIds and storeId are required"})
                data = await client.delete("/dsers-product-bff/my-product", **params)
                return reply(data)

            # --- Mapping ---
            if name == "dsers_get_mapping":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                data = await client.get(f"/dsers-product-bff/mapping/{pid}")
                return reply(data)

            if name == "dsers_create_variant_mapping":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                body = arguments.get("mapping") or {k: v for k, v in arguments.items() if k != "dsers_product_id" and v is not None}
                data = await client.post(f"/dsers-product-bff/mapping/{pid}", json=body)
                return reply(data)

            if name == "dsers_delete_mapping":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                data = await client.delete(f"/dsers-product-bff/mapping/{pid}")
                return reply(data)

            if name == "dsers_get_mapped_suppliers":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                data = await client.get(f"/dsers-product-bff/mapping/{pid}/suppliers")
                return reply(data)

            if name == "dsers_get_mapping_pool":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                params = _params(arguments, "mappingType")
                data = await client.get(f"/dsers-product-bff/mapping/{pid}/pool", **params)
                return reply(data)

            if name == "dsers_import_mapping_pool":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                body = arguments.get("supplyProduct") or {k: v for k, v in arguments.items() if k != "dsers_product_id" and v is not None}
                data = await client.post(f"/dsers-product-bff/mapping/{pid}/pool", json=body)
                return reply(data)

            if name == "dsers_check_mapping_status":
                pid = arguments.get("dsers_product_id")
                if not pid:
                    return reply({"error": "dsers_product_id is required"})
                data = await client.get(f"/dsers-product-bff/mapping/check-process-status/{pid}")
                return reply(data)

            if name == "dsers_search_mapping_products":
                params = _params(arguments, "keyword", "storeId", "page", "pageSize")
                data = await client.get("/dsers-product-bff/mapping-list", **params)
                return reply(data)

            # --- Product Pool ---
            if name == "dsers_get_pool_product_detail":
                params = _params(arguments, "productId", "appId", "shipTo")
                if not all(params.get(k) for k in ("productId", "appId", "shipTo")):
                    return reply({"error": "productId, appId, and shipTo are required"})
                data = await client.get("/dsers-product-bff/product-pool/product/detail", **params)
                return reply(data)

            if name == "dsers_get_pool_product_logistics":
                params = _params(arguments, "productId", "appId", "shipTo", "country")
                if not all(params.get(k) for k in ("productId", "appId", "shipTo")):
                    return reply({"error": "productId, appId, and shipTo are required"})
                data = await client.get("/dsers-product-bff/product-pool/product/logistics", **params)
                return reply(data)

            if name == "dsers_search_product_pool":
                params = _params(arguments, "keyword", "category", "page", "pageSize")
                data = await client.get("/dsers-product-bff/product-pool/products", **params)
                return reply(data)

            # --- Find Suppliers ---
            if name == "dsers_find_suppliers":
                params = _params(
                    arguments,
                    "supplyAppId", "keyword", "shipTo", "shipFrom", "minPrice", "maxPrice",
                    "sort", "limit", "searchAfter", "categoryId", "deliveryTime", "language", "agentType",
                )
                if not params.get("supplyAppId"):
                    return reply({"error": "supplyAppId is required"})
                data = await client.get("/dsers-product-bff/find-suppliers/products", **params)
                return reply(data)

            if name == "dsers_find_suppliers_by_image":
                params = _params(arguments, "imgUrl", "shipFrom", "shipTo", "appId")
                if not params.get("imgUrl"):
                    return reply({"error": "imgUrl is required"})
                data = await client.get("/dsers-product-bff/find-suppliers/products/search-by-picture", **params)
                return reply(data)

            if name == "dsers_get_supplier_categories":
                params = _params(arguments, "supplierAppId")
                if not params.get("supplierAppId"):
                    return reply({"error": "supplierAppId is required"})
                data = await client.get("/dsers-product-bff/find-suppliers/categories", **params)
                return reply(data)

            if name == "dsers_get_ship_from_list":
                params = _params(arguments, "supplyAppId")
                if not params.get("supplyAppId"):
                    return reply({"error": "supplyAppId is required"})
                data = await client.get("/dsers-product-bff/find-suppliers/ship-from", **params)
                return reply(data)

            # --- URL Parsing ---
            if name == "dsers_parse_product_url":
                body = {
                    "url": arguments.get("url"),
                    "appId": arguments.get("appId"),
                }
                if not body["url"] or body["appId"] is None:
                    return reply({"error": "url and appId are required"})
                data = await client.post("/dsers-product-bff/supplier/parse-product-url", json=body)
                return reply(data)

            return reply({"error": f"Unknown tool: {name}"})

        except Exception as e:
            err_msg = str(e)
            err_detail = getattr(e, "body", None)
            status = getattr(e, "status", None)
            out: dict[str, Any] = {"error": err_msg}
            if status is not None:
                out["status"] = status
            if err_detail:
                out["detail"] = err_detail
            return reply(out)

    return TOOLS, handle
