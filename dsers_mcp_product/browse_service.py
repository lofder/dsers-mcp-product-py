"""Browse & search service — wraps provider methods with validation, truncation, and formatting."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .browse_shared import cents_to_dollars, derive_supplier, build_supplier_url, ALIEXPRESS_APP_ID


SORT_MAP = {"relevance": 0, "newest": 1, "price": 2}


async def discover_products(provider: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Search the DSers product pool by keyword or image URL."""
    keyword = (params.get("keyword") or "").strip()
    image_url = (params.get("image_url") or "").strip()

    if not keyword and not image_url:
        raise ValueError("Either keyword or image_url must be provided for product search.")
    if "keyword" in params and not keyword and not image_url:
        raise ValueError("keyword cannot be empty or whitespace-only. Provide a non-empty search term or use image_url.")

    effective_limit = int(params.get("limit") or 20)

    raw = await provider.find_products({
        "keyword": keyword or None,
        "image_url": image_url or None,
        "limit": effective_limit,
        "search_after": params.get("search_after"),
        "sort": SORT_MAP.get(params.get("sort", ""), 0),
        "ship_to": params.get("ship_to", "US"),
        "ship_from": params.get("ship_from"),
        "category_id": params.get("category_id"),
    })

    pool: List[Dict[str, Any]] = raw.get("items") or []
    search_after: str = raw.get("search_after") or ""

    truncated = len(pool) > effective_limit
    capped = pool[:effective_limit] if truncated else pool

    items = [
        {
            "product_id": str(p.get("product_id") or ""),
            "title": p.get("title") or "",
            "image": p.get("image") or "",
            "price": {
                "min": cents_to_dollars(p.get("min_price") or 0),
                "max": cents_to_dollars(p.get("max_price") or 0),
            },
            "rating": p.get("rating") or 0,
            "orders": p.get("orders") or 0,
            "shipping_cost": cents_to_dollars(p.get("logistics_cost") or 0),
            "supplier": derive_supplier(p.get("app_id")),
            "import_url": f"https://www.aliexpress.com/item/{p.get('product_id', '')}.html",
        }
        for p in capped
    ]

    result: Dict[str, Any] = {
        "items": items,
        "search_after": search_after,
        "has_more": len(pool) > 0 and search_after != "",
    }

    if truncated:
        result["truncated_from"] = len(pool)

    if search_after:
        result["pagination_note"] = "Results may overlap between pages. Deduplicate by product_id if needed."

    if len(items) < effective_limit and not search_after:
        result["note"] = "Fewer results than requested. The product pool may have limited coverage for this query."

    return result


async def browse_import_list(provider: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Browse the DSers import list with enriched variant data."""
    page = max(1, int(params.get("page") or 1))
    page_size = max(1, min(int(params.get("page_size") or 20), 100))

    raw = await provider.list_import_items({"page": page, "page_size": page_size})
    items = raw.get("items") or []
    total = raw.get("total") or len(items)

    return {"page": page, "page_size": page_size, "total": total, "items": items}


async def browse_my_products(provider: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Browse products already pushed to a store."""
    store_id = params.get("store_id")
    if not store_id:
        raise ValueError("store_id is required. Get it from dsers_store_discover.")

    page = max(1, int(params.get("page") or 1))
    page_size = max(1, min(int(params.get("page_size") or 20), 100))

    raw = await provider.list_my_products({"store_id": store_id, "page": page, "page_size": page_size})
    items = raw.get("items") or []
    total = raw.get("total") or len(items)

    return {"page": page, "page_size": page_size, "total": total, "items": items}


async def delete_import_item(provider: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a product from the DSers import list."""
    import_item_id = str(params.get("import_item_id") or "").strip()
    if not import_item_id:
        raise ValueError("import_item_id is required. Get it from dsers_import_list or dsers_product_preview.")

    confirm = params.get("confirm", False)
    if not confirm:
        return {
            "action": "confirm_required",
            "import_item_id": import_item_id,
            "message": "This will permanently delete the product from the DSers import list. "
                       "Call again with confirm=true to proceed. "
                       "Products already pushed to Shopify/Wix are NOT affected.",
        }

    await provider.delete_import_item(import_item_id)
    return {"deleted": True, "import_item_id": import_item_id}
