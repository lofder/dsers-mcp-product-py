"""Tests for browse/search service and shared helpers."""
import asyncio
import pytest

from dsers_mcp_product.browse_shared import cents_to_dollars, derive_supplier, build_supplier_url
from dsers_mcp_product.browse_service import discover_products, browse_import_list, browse_my_products, delete_import_item
from dsers_mcp_product.mock_provider import MockImportProvider


class TestBrowseShared:
    def test_cents_to_dollars_normal(self):
        assert cents_to_dollars(1500) == 15.0

    def test_cents_to_dollars_none(self):
        assert cents_to_dollars(None) is None

    def test_cents_to_dollars_zero(self):
        assert cents_to_dollars(0) == 0.0

    def test_derive_supplier_aliexpress(self):
        assert derive_supplier("159831080") == "aliexpress"

    def test_derive_supplier_unknown(self):
        assert derive_supplier("999") == "unknown"

    def test_build_supplier_url_aliexpress(self):
        url = build_supplier_url("12345", "aliexpress")
        assert "aliexpress.com/item/12345" in url

    def test_build_supplier_url_empty(self):
        assert build_supplier_url(None, "aliexpress") == ""


class TestDiscoverProducts:
    def test_empty_keyword_raises(self):
        provider = MockImportProvider()
        with pytest.raises(ValueError, match="keyword or image_url"):
            asyncio.run(discover_products(provider, {}))

    def test_whitespace_keyword_raises(self):
        provider = MockImportProvider()
        with pytest.raises(ValueError):
            asyncio.run(discover_products(provider, {"keyword": "   "}))

    def test_returns_items(self):
        provider = MockImportProvider()
        result = asyncio.run(discover_products(provider, {"keyword": "phone case"}))
        assert len(result["items"]) > 0
        assert "product_id" in result["items"][0]

    def test_truncation(self):
        """When pool has more items than limit, truncated_from should be set."""
        class BigPoolProvider(MockImportProvider):
            async def find_products(self, params):
                items = [{"product_id": str(i), "title": f"P{i}", "min_price": 100, "max_price": 200,
                          "rating": 5, "orders": 10, "logistics_cost": 0, "app_id": "159831080"} for i in range(19)]
                return {"items": items, "search_after": "cursor"}

        provider = BigPoolProvider()
        result = asyncio.run(discover_products(provider, {"keyword": "test", "limit": 3}))
        assert len(result["items"]) == 3
        assert result["truncated_from"] == 19

    def test_insufficient_results_note(self):
        provider = MockImportProvider()
        result = asyncio.run(discover_products(provider, {"keyword": "rare item", "limit": 10}))
        assert "note" in result


class TestBrowseImportList:
    def test_returns_items(self):
        provider = MockImportProvider()
        result = asyncio.run(browse_import_list(provider, {}))
        assert result["total"] >= 0
        assert isinstance(result["items"], list)


class TestBrowseMyProducts:
    def test_requires_store_id(self):
        provider = MockImportProvider()
        with pytest.raises(ValueError, match="store_id"):
            asyncio.run(browse_my_products(provider, {}))


class TestDeleteImportItem:
    def test_requires_confirm(self):
        provider = MockImportProvider()
        result = asyncio.run(delete_import_item(provider, {"import_item_id": "test-123"}))
        assert result["action"] == "confirm_required"

    def test_deletes_with_confirm(self):
        provider = MockImportProvider()
        result = asyncio.run(delete_import_item(provider, {"import_item_id": "test-123", "confirm": True}))
        assert result["deleted"] is True

    def test_missing_id_raises(self):
        provider = MockImportProvider()
        with pytest.raises(ValueError, match="import_item_id"):
            asyncio.run(delete_import_item(provider, {}))
