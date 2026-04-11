"""Tests for SKU variant matching engine."""
import asyncio
import pytest
from dsers_mcp_product.sku_matcher import match_variants, VariantForMatch, _normalize_value, _score_pair


def _v(title, option_values=None, price=None, stock=10, image=None):
    return VariantForMatch(
        variant_ref=title,
        title=title,
        option_values=option_values or [],
        supplier_price=price,
        stock=stock,
        image_url=image,
    )


class TestNormalizeValue:
    def test_lowercase_strip(self):
        assert _normalize_value("  Red  ") == "red"

    def test_synonym_small(self):
        assert _normalize_value("S") == "small"

    def test_synonym_xl(self):
        assert _normalize_value("XL") == "extra large"


class TestScorePair:
    def test_exact_match_high_confidence(self):
        sv = _v("Red / S", [{"option_name": "Color", "value_name": "Red"}, {"option_name": "Size", "value_name": "S"}])
        cv = _v("Red / S", [{"option_name": "Color", "value_name": "Red"}, {"option_name": "Size", "value_name": "S"}])
        conf, reasons = asyncio.run(_score_pair(sv, cv))
        assert conf >= 80

    def test_normalized_match(self):
        sv = _v("red / small", [{"option_name": "Color", "value_name": "Red"}])
        cv = _v("RED / SMALL", [{"option_name": "Color", "value_name": "red"}])
        conf, _ = asyncio.run(_score_pair(sv, cv))
        assert conf >= 70

    def test_no_match_low_confidence(self):
        sv = _v("Red", [{"option_name": "Color", "value_name": "Red"}])
        cv = _v("Blue", [{"option_name": "Color", "value_name": "Blue"}])
        conf, _ = asyncio.run(_score_pair(sv, cv))
        assert conf < 50

    def test_synonym_match(self):
        sv = _v("S", [{"option_name": "Size", "value_name": "S"}])
        cv = _v("Small", [{"option_name": "Size", "value_name": "Small"}])
        conf, _ = asyncio.run(_score_pair(sv, cv))
        assert conf >= 60


class TestMatchVariants:
    def test_perfect_match(self):
        store = [_v("Red", [{"option_name": "Color", "value_name": "Red"}]),
                 _v("Blue", [{"option_name": "Color", "value_name": "Blue"}])]
        cand = [_v("Red", [{"option_name": "Color", "value_name": "Red"}]),
                _v("Blue", [{"option_name": "Color", "value_name": "Blue"}])]
        result = asyncio.run(match_variants(store, cand, auto_confidence=50))
        assert len(result.matches) == 2
        assert len(result.unmatched_store) == 0

    def test_partial_match(self):
        store = [_v("Red", [{"option_name": "Color", "value_name": "Red"}]),
                 _v("Green", [{"option_name": "Color", "value_name": "Green"}])]
        cand = [_v("Red", [{"option_name": "Color", "value_name": "Red"}])]
        result = asyncio.run(match_variants(store, cand, auto_confidence=50))
        assert len(result.matches) == 1
        assert len(result.unmatched_store) == 1

    def test_no_match_below_threshold(self):
        store = [_v("Red", [{"option_name": "Color", "value_name": "Red"}])]
        cand = [_v("Blue", [{"option_name": "Color", "value_name": "Blue"}])]
        result = asyncio.run(match_variants(store, cand, auto_confidence=90))
        assert len(result.matches) == 0
        assert len(result.unmatched_store) == 1
