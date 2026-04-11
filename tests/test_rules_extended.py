"""Tests for extended rule families: fixed_price, variant_overrides, option_edits, merge_rules."""
import pytest
from dsers_mcp_product.rules import normalize_rules, apply_rules, merge_rules


def _mk_draft(variants=None, extra=None):
    d = {
        "title": "Original Title",
        "description_html": "<p>Original</p>",
        "tags": ["existing"],
        "images": ["img1.jpg", "img2.jpg"],
        "variants": variants or [],
        "options": [],
    }
    if extra:
        d.update(extra)
    return d


def _mk_variant(supplier=None, offer=None, title="V", sku="V"):
    return {"variant_ref": title, "title": title, "supplier_price": supplier, "offer_price": offer, "sku": sku, "stock": 10}


# ═══════════════════════════════════════════════════
# fixed_price pricing mode
# ═══════════════════════════════════════════════════

class TestFixedPrice:
    def test_fixed_price_applies_to_all_variants(self):
        draft = _mk_draft([_mk_variant(4.0, 10.0, "A"), _mk_variant(6.0, 12.0, "B")])
        result = apply_rules(draft, {"pricing": {"mode": "fixed_price", "fixed_price": 9.99}})
        for v in result["draft"]["variants"]:
            assert v["offer_price"] == 9.99

    def test_fixed_price_zero_produces_warning(self):
        result = normalize_rules({"pricing": {"mode": "fixed_price", "fixed_price": 0}})
        assert any("$0" in w for w in result["warnings"])
        assert not result["errors"]

    def test_fixed_price_negative_produces_error(self):
        result = normalize_rules({"pricing": {"mode": "fixed_price", "fixed_price": -5}})
        assert result["errors"]

    def test_fixed_price_extreme_warning(self):
        result = normalize_rules({"pricing": {"mode": "fixed_price", "fixed_price": 50000}})
        assert any("50000" in w for w in result["warnings"])

    def test_fixed_price_normal_no_warning(self):
        result = normalize_rules({"pricing": {"mode": "fixed_price", "fixed_price": 29.99}})
        assert not any("unusually high" in w for w in result["warnings"])


# ═══════════════════════════════════════════════════
# variant_overrides
# ═══════════════════════════════════════════════════

class TestVariantOverrides:
    def test_match_by_title(self):
        draft = _mk_draft([_mk_variant(4.0, 10.0, "Red"), _mk_variant(6.0, 12.0, "Blue")])
        result = apply_rules(draft, {"variant_overrides": [{"match": "Red", "sell_price": 5.0}]})
        assert result["draft"]["variants"][0]["offer_price"] == 5.0
        assert result["draft"]["variants"][1]["offer_price"] == 12.0  # unchanged

    def test_match_by_sku(self):
        draft = _mk_draft([_mk_variant(4.0, 10.0, "V1", "SKU-RED")])
        result = apply_rules(draft, {"variant_overrides": [{"match": "sku-red", "sell_price": 7.0}]})
        assert result["draft"]["variants"][0]["offer_price"] == 7.0

    def test_no_match_produces_warning(self):
        draft = _mk_draft([_mk_variant(4.0, 10.0, "Red")])
        result = apply_rules(draft, {"variant_overrides": [{"match": "Green", "sell_price": 5.0}]})
        assert any("no variants matched" in w for w in result["summary"]["warnings"])

    def test_missing_match_field_error(self):
        result = normalize_rules({"variant_overrides": [{"sell_price": 5.0}]})
        assert result["errors"]

    def test_compare_at_price(self):
        draft = _mk_draft([_mk_variant(4.0, 10.0, "Red")])
        result = apply_rules(draft, {"variant_overrides": [{"match": "Red", "compare_at_price": 19.99}]})
        assert result["draft"]["variants"][0]["compare_at_price"] == 19.99


# ═══════════════════════════════════════════════════
# option_edits
# ═══════════════════════════════════════════════════

class TestOptionEdits:
    def _mk_option_draft(self):
        return _mk_draft(
            variants=[
                {"variant_ref": "v1", "title": "Red / S", "sku": "RS", "offer_price": 10, "stock": 5,
                 "option_values": [{"optionId": "opt1", "optionName": "Color", "valueId": "c1", "valueName": "Red"},
                                   {"optionId": "opt2", "optionName": "Size", "valueId": "s1", "valueName": "S"}]},
                {"variant_ref": "v2", "title": "Blue / S", "sku": "BS", "offer_price": 12, "stock": 3,
                 "option_values": [{"optionId": "opt1", "optionName": "Color", "valueId": "c2", "valueName": "Blue"},
                                   {"optionId": "opt2", "optionName": "Size", "valueId": "s1", "valueName": "S"}]},
            ],
            extra={
                "options": [
                    {"id": "opt1", "name": "Color", "values": [{"id": "c1", "name": "Red"}, {"id": "c2", "name": "Blue"}]},
                    {"id": "opt2", "name": "Size", "values": [{"id": "s1", "name": "S"}]},
                ]
            },
        )

    def test_rename_option(self):
        draft = self._mk_option_draft()
        result = apply_rules(draft, {"option_edits": [{"action": "rename_option", "option_name": "Color", "new_name": "Colour"}]})
        opts = result["draft"]["options"]
        assert opts[0]["name"] == "Colour"

    def test_rename_value(self):
        draft = self._mk_option_draft()
        result = apply_rules(draft, {"option_edits": [{"action": "rename_value", "option_name": "Color", "value_name": "Red", "new_name": "Crimson"}]})
        vals = result["draft"]["options"][0]["values"]
        assert vals[0]["name"] == "Crimson"
        assert "Crimson" in result["draft"]["variants"][0]["title"]

    def test_remove_value_deletes_variants(self):
        draft = self._mk_option_draft()
        result = apply_rules(draft, {"option_edits": [{"action": "remove_value", "option_name": "Color", "value_name": "Red"}]})
        assert len(result["draft"]["variants"]) == 1
        assert result["draft"]["variants"][0]["sku"] == "BS"

    def test_remove_option(self):
        draft = self._mk_option_draft()
        result = apply_rules(draft, {"option_edits": [{"action": "remove_option", "option_name": "Size"}]})
        assert len(result["draft"]["options"]) == 1
        assert result["draft"]["options"][0]["name"] == "Color"

    def test_unknown_action_error(self):
        result = normalize_rules({"option_edits": [{"action": "unknown_action", "option_name": "Color"}]})
        assert result["errors"]

    def test_not_found_option_warning(self):
        draft = self._mk_option_draft()
        result = apply_rules(draft, {"option_edits": [{"action": "rename_option", "option_name": "Material", "new_name": "Fabric"}]})
        assert any("not found" in w for w in result["summary"]["warnings"])


# ═══════════════════════════════════════════════════
# merge_rules
# ═══════════════════════════════════════════════════

class TestMergeRules:
    def test_pricing_replaces_entire_family(self):
        existing = {"pricing": {"mode": "multiplier", "multiplier": 2}, "content": {"title_prefix": "[US] "}}
        incoming = {"pricing": {"mode": "fixed_price", "fixed_price": 9.99}}
        merged = merge_rules(existing, incoming)
        assert merged["pricing"]["mode"] == "fixed_price"
        assert merged["content"]["title_prefix"] == "[US] "  # preserved

    def test_content_merges_by_field(self):
        existing = {"content": {"title_prefix": "[US] ", "description_override_html": "<p>old</p>"}}
        incoming = {"content": {"title_prefix": "[EU] "}}
        merged = merge_rules(existing, incoming)
        assert merged["content"]["title_prefix"] == "[EU] "
        assert merged["content"]["description_override_html"] == "<p>old</p>"  # preserved

    def test_null_removes_family(self):
        existing = {"pricing": {"mode": "multiplier", "multiplier": 2}, "content": {"title_prefix": "X"}}
        incoming = {"pricing": None}
        merged = merge_rules(existing, incoming)
        assert "pricing" not in merged
        assert merged["content"]["title_prefix"] == "X"

    def test_content_empty_string_removes_field(self):
        existing = {"content": {"title_prefix": "[US] ", "title_suffix": " - Sale"}}
        incoming = {"content": {"title_prefix": ""}}
        merged = merge_rules(existing, incoming)
        assert "title_prefix" not in merged["content"]
        assert merged["content"]["title_suffix"] == " - Sale"
