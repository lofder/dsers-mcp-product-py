"""Push safety guard — validates pricing and stock before pushing to store."""
from __future__ import annotations
from typing import Any, Dict, List, Optional


LOW_STOCK_THRESHOLD = 5
LOW_PRICE_THRESHOLD = 1.0  # $1.00 (dollars)
LOW_MARGIN_RATIO = 0.1     # 10%


def _fmt_dollars(price: float) -> str:
    return f"${price:.2f}"


def validate_push_safety(
    draft: Dict[str, Any],
    original_draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    """Check draft for dangerous pricing/stock issues before push.

    Returns {"blocked": [...], "warnings": [...]}.
    blocked = hard stop (must fix before push)
    warnings = informational (push proceeds)
    """
    blocked: List[str] = []
    warnings: List[str] = []
    variants = draft.get("variants") or []

    if not variants:
        warnings.append("No variants in draft — nothing to push.")
        return {"blocked": blocked, "warnings": warnings}

    all_zero_stock = True
    total_stock = 0

    for v in variants:
        label = v.get("title") or v.get("variant_ref") or "unknown"
        offer = _to_num(v.get("offer_price"))
        cost = _to_num(v.get("supplier_price"))
        stock = _to_num(v.get("stock"))

        # Zero or negative price → blocked
        if offer is not None and offer <= 0:
            blocked.append(
                f'Variant "{label}" has zero or negative sell price ({_fmt_dollars(offer)}). '
                "Fix pricing with dsers_product_update_rules before pushing."
            )

        # Below cost → blocked
        if offer is not None and cost is not None and offer > 0 and cost > 0 and offer < cost:
            blocked.append(
                f'Variant "{label}" sell price ({_fmt_dollars(offer)}) is below cost ({_fmt_dollars(cost)}). '
                "You will lose money on every sale."
            )

        # Low margin → warning
        if offer is not None and cost is not None and cost > 0 and offer > cost:
            margin = (offer - cost) / cost
            if margin < LOW_MARGIN_RATIO:
                warnings.append(
                    f'Variant "{label}" has low margin: sell {_fmt_dollars(offer)} vs cost {_fmt_dollars(cost)} '
                    f"({margin:.0%}). Consider increasing the price."
                )

        # Very low price → warning
        if offer is not None and 0 < offer < LOW_PRICE_THRESHOLD:
            warnings.append(
                f'Variant "{label}" has a very low price: {_fmt_dollars(offer)}. Is this intentional?'
            )

        # Stock tracking
        if stock is not None:
            total_stock += int(stock)
            if stock > 0:
                all_zero_stock = False
        else:
            all_zero_stock = False  # unknown stock ≠ zero stock

    # All variants zero stock → blocked
    if all_zero_stock and total_stock == 0:
        blocked.append(
            "All variants have zero stock. The product cannot be sold. "
            "Check supplier availability or update stock via variant_overrides."
        )

    # Low total stock → warning
    if 0 < total_stock < LOW_STOCK_THRESHOLD:
        warnings.append(
            f"Total stock is very low ({total_stock} units across all variants)."
        )

    return {"blocked": blocked, "warnings": warnings}


def _to_num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
