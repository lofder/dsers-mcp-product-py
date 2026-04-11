"""Tests for push safety guard."""
import pytest
from dsers_mcp_product.push_guard import validate_push_safety


def _mk_variant(offer=10.0, cost=5.0, stock=10, title="V"):
    return {"title": title, "offer_price": offer, "supplier_price": cost, "stock": stock}


class TestPushGuard:
    def test_zero_price_blocked(self):
        r = validate_push_safety({"variants": [_mk_variant(offer=0)]})
        assert any("zero or negative" in b for b in r["blocked"])

    def test_negative_price_blocked(self):
        r = validate_push_safety({"variants": [_mk_variant(offer=-1)]})
        assert r["blocked"]

    def test_below_cost_blocked(self):
        r = validate_push_safety({"variants": [_mk_variant(offer=2.0, cost=5.0)]})
        assert any("below cost" in b for b in r["blocked"])

    def test_all_zero_stock_blocked(self):
        r = validate_push_safety({"variants": [_mk_variant(stock=0), _mk_variant(stock=0)]})
        assert any("zero stock" in b for b in r["blocked"])

    def test_low_margin_warning(self):
        r = validate_push_safety({"variants": [_mk_variant(offer=5.4, cost=5.0)]})
        assert any("low margin" in w for w in r["warnings"])

    def test_very_low_price_warning(self):
        r = validate_push_safety({"variants": [_mk_variant(offer=0.50, cost=0.20)]})
        assert any("very low price" in w for w in r["warnings"])

    def test_healthy_variant_passes(self):
        r = validate_push_safety({"variants": [_mk_variant(offer=15.0, cost=5.0, stock=50)]})
        assert not r["blocked"]
        assert not r["warnings"]

    def test_low_stock_warning(self):
        r = validate_push_safety({"variants": [_mk_variant(stock=2)]})
        assert any("low" in w.lower() and "stock" in w.lower() for w in r["warnings"])

    def test_no_variants_warning(self):
        r = validate_push_safety({"variants": []})
        assert any("No variants" in w for w in r["warnings"])
