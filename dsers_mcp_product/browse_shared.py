"""Shared helpers for browse/search tools — cents conversion, supplier detection, URL builders."""
from __future__ import annotations

from typing import Optional, Union

ALIEXPRESS_APP_ID = "159831080"
ALIBABA_APP_ID = "1902659021782450176"
ALIEXPRESS_APP_IDS = {ALIEXPRESS_APP_ID}
ALIBABA_APP_IDS = {ALIBABA_APP_ID}


def cents_to_dollars(cents: Optional[Union[float, int]]) -> Optional[float]:
    if cents is None:
        return None
    return round(int(cents)) / 100


def derive_supplier(supply_app_id: Optional[Union[str, int]]) -> str:
    sid = str(supply_app_id or "")
    if sid in ALIEXPRESS_APP_IDS:
        return "aliexpress"
    if sid in ALIBABA_APP_IDS:
        return "alibaba"
    return "unknown"


def build_supplier_url(supply_product_id: Optional[str], supplier: str) -> str:
    if not supply_product_id:
        return ""
    if supplier == "aliexpress":
        return f"https://www.aliexpress.com/item/{supply_product_id}.html"
    if supplier == "alibaba":
        return f"https://www.alibaba.com/product-detail/_{supply_product_id}.html"
    return ""
