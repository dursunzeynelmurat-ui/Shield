"""
Integration test: connector → ingest → DB → catalog search pipeline.

Validates:
1. Connector search() returns correct output format
2. ingest_batch() stores products + merchant_offers + price_history
3. catalog search returns the ingested products
4. live_search_and_seed() wires all of the above together
5. GenericConnector.search() aggregates from all registered connectors
6. Price history is recorded on ingest and on price update
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, MerchantOffer, PriceHistory, Product
from app.catalog.ingest import ingest_batch
from app.catalog.service import search_products
from app.merchants.connector import (
    TrendyolConnector,
    HepsiburadaConnector,
    GenericConnector,
    _normalize_title,
    _CONNECTORS,
)

# ── In-memory SQLite ─────────────────────────────────────────────────────────

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Raw DDL for tables needed by these tests.
# SQLite only auto-increments INTEGER PRIMARY KEY (not BIGINT), so we create
# tables with explicit INTEGER to get rowid aliasing.  We do NOT use
# Base.metadata.create_all() to avoid mutating the shared metadata and
# breaking other test files that import the same Base.
_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT,
    path TEXT,
    depth INTEGER DEFAULT 0,
    parent_id INTEGER REFERENCES categories(id),
    source_map TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT,
    brand TEXT,
    model TEXT,
    category TEXT,
    category_id INTEGER REFERENCES categories(id),
    description TEXT,
    image_url TEXT,
    ean TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_normalized_name
    ON products (normalized_name);
CREATE TABLE IF NOT EXISTS merchant_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    merchant TEXT NOT NULL,
    seller_name TEXT,
    url TEXT,
    listed_price NUMERIC(12,2),
    shipping_price NUMERIC(12,2),
    effective_price NUMERIC(12,2),
    currency TEXT DEFAULT 'TRY',
    in_stock BOOLEAN DEFAULT 1,
    last_checked_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (product_id, merchant, seller_name)
);
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    merchant TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'TRY',
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest_asyncio.fixture(scope="function")
async def db():
    from sqlalchemy import text
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in _CREATE_TABLES_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


# ── Fixtures: realistic connector payloads ───────────────────────────────────

TRENDYOL_API_PAYLOAD = {
    "result": {
        "products": [
            {
                "name": "Samsung Galaxy A55 5G 256 GB Akıllı Telefon",
                "url": "/samsung/galaxy-a55-5g-256-gb-p-814726949",
                "merchantName": "Samsung Türkiye",
                "price": {"discountedPrice": 14999.99, "sellingPrice": 17999.00},
                "imageUrl": "https://cdn.dsmcdn.com/ty1234/product/media/images/fake.jpg",
            },
            {
                "name": "Samsung Galaxy A35 5G 128 GB",
                "url": "/samsung/galaxy-a35-5g-128-gb-p-123456",
                "merchantName": "MediaMarkt",
                "price": {"discountedPrice": 11499.00, "sellingPrice": 12999.00},
                "imageUrl": "https://cdn.dsmcdn.com/ty1234/product/media/images/fake2.jpg",
            },
        ]
    }
}

HB_NEXT_DATA_PAYLOAD = {
    "props": {
        "pageProps": {
            "products": [
                {
                    "name": "Apple iPhone 15 128GB Siyah",
                    "url": "apple-iphone-15-128gb-siyah-p-HBCV00003RJKKV",
                    "merchantName": "Hepsiburada",
                    "price": 44999.00,
                    "imageUrl": "https://productimages.hepsiburada.net/s/fake.jpg",
                },
                {
                    "name": "Apple iPhone 15 256GB Mavi",
                    "url": "apple-iphone-15-256gb-mavi-p-HBCV00003RJKKZ",
                    "merchantName": "iStore",
                    "price": 54999.00,
                    "imageUrl": "https://productimages.hepsiburada.net/s/fake2.jpg",
                },
            ]
        }
    }
}


# ── Helper: build fake HTML ───────────────────────────────────────────────────

def _ty_html(payload: dict) -> str:
    import json
    return f'<html><head></head><body><script>window.__SEARCH_APP_INITIAL_STATE__ = {json.dumps(payload)}; </script></body></html>'


def _hb_html(payload: dict) -> str:
    import json
    return f'<html><head></head><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></body></html>'


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNormalizeTitle:
    def test_turkish_chars(self):
        assert _normalize_title("Şarj Kablosu") == "sarj kablosu"

    def test_collapses_whitespace(self):
        assert _normalize_title("  iPhone  15  Pro  ") == "iphone 15 pro"

    def test_strips_punctuation(self):
        assert _normalize_title("Samsung Galaxy (A55)") == "samsung galaxy a55"


class TestTrendyolConnector:
    def test_parse_api_results_format(self):
        connector = TrendyolConnector()
        results = connector._parse_api_results(TRENDYOL_API_PAYLOAD)
        assert len(results) == 2

        r = results[0]
        assert r["title"] == "Samsung Galaxy A55 5G 256 GB Akıllı Telefon"
        assert r["normalized_title"] == "samsung galaxy a55 5g 256 gb akilli telefon"
        assert r["price"] == Decimal("14999.99")
        assert r["currency"] == "TRY"
        assert r["seller"] == "Samsung Türkiye"
        assert "trendyol.com" in r["url"]
        assert r["merchant"] == "trendyol"
        assert "product_url" in r

    def test_parse_html_results_format(self):
        connector = TrendyolConnector()
        # __SEARCH_APP_INITIAL_STATE__ wraps same product list
        state_payload = {"products": TRENDYOL_API_PAYLOAD["result"]["products"]}
        html = _ty_html(state_payload)
        results = connector._parse_html_results(html)
        assert len(results) == 2
        assert results[0]["merchant"] == "trendyol"
        assert results[0]["normalized_title"] is not None

    def test_skips_empty_title(self):
        connector = TrendyolConnector()
        data = {"result": {"products": [{"name": "", "url": "/foo", "price": {}}]}}
        results = connector._parse_api_results(data)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_mock_api(self):
        """Full search() method with mocked HTTP — verifies retry logic path."""
        import json
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TRENDYOL_API_PAYLOAD

        with patch("app.merchants.connector._fetch_html", new=AsyncMock(return_value=mock_response)):
            connector = TrendyolConnector()
            results = await connector.search("samsung galaxy", "Samsung", None)

        assert len(results) == 2
        assert results[0]["title"] == "Samsung Galaxy A55 5G 256 GB Akıllı Telefon"
        assert results[0]["price"] == Decimal("14999.99")

    @pytest.mark.asyncio
    async def test_search_retries_on_none(self):
        """When API returns None (failed), falls through to HTML; HTML also None → empty."""
        with patch("app.merchants.connector._fetch_html", new=AsyncMock(return_value=None)):
            connector = TrendyolConnector()
            results = await connector.search("samsung", None, None)
        assert results == []


class TestHepsiburadaConnector:
    def test_parse_search_next_data(self):
        connector = HepsiburadaConnector()
        html = _hb_html(HB_NEXT_DATA_PAYLOAD)
        results = connector._parse_search(html)
        assert len(results) == 2
        r = results[0]
        assert r["title"] == "Apple iPhone 15 128GB Siyah"
        assert r["normalized_title"] == "apple iphone 15 128gb siyah"
        assert r["price"] == Decimal("44999.00")
        assert r["merchant"] == "hepsiburada"
        assert "hepsiburada.com" in r["url"]

    @pytest.mark.asyncio
    async def test_search_with_mock(self):
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _hb_html(HB_NEXT_DATA_PAYLOAD)

        with patch("app.merchants.connector._fetch_html", new=AsyncMock(return_value=mock_response)):
            connector = HepsiburadaConnector()
            results = await connector.search("iphone 15", "Apple", None)

        assert len(results) == 2
        assert results[0]["merchant"] == "hepsiburada"


class TestGenericConnector:
    @pytest.mark.asyncio
    async def test_aggregates_from_all_connectors(self):
        """GenericConnector.search() calls all registered connectors and merges."""
        ty_results = [
            {"title": "Samsung A55", "normalized_title": "samsung a55",
             "price": Decimal("14999"), "currency": "TRY", "url": "https://ty.com/p/1",
             "seller": "Samsung TR", "merchant": "trendyol", "image_url": None, "product_url": "https://ty.com/p/1"},
        ]
        hb_results = [
            {"title": "Samsung Galaxy A55 5G", "normalized_title": "samsung galaxy a55 5g",
             "price": Decimal("15200"), "currency": "TRY", "url": "https://hb.com/p/2",
             "seller": "Hepsiburada", "merchant": "hepsiburada", "image_url": None, "product_url": "https://hb.com/p/2"},
        ]

        with patch.object(TrendyolConnector, "search", new=AsyncMock(return_value=ty_results)), \
             patch.object(HepsiburadaConnector, "search", new=AsyncMock(return_value=hb_results)):
            connector = GenericConnector()
            results = await connector.search("samsung a55", "Samsung", None)

        assert len(results) == 2
        titles = {r["title"] for r in results}
        assert "Samsung A55" in titles
        assert "Samsung Galaxy A55 5G" in titles

    @pytest.mark.asyncio
    async def test_deduplicates_same_normalized_title(self):
        same = [
            {"title": "Samsung A55", "normalized_title": "samsung a55",
             "price": Decimal("14999"), "currency": "TRY", "url": "https://ty.com/p/1",
             "seller": "X", "merchant": "trendyol", "image_url": None, "product_url": "https://ty.com/p/1"},
        ]
        with patch.object(TrendyolConnector, "search", new=AsyncMock(return_value=same)), \
             patch.object(HepsiburadaConnector, "search", new=AsyncMock(return_value=same)):
            connector = GenericConnector()
            results = await connector.search("samsung a55", None, None)
        # Same normalized_title → deduplicated to 1
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_handles_connector_exception(self):
        """GenericConnector skips connectors that raise exceptions."""
        with patch.object(TrendyolConnector, "search", new=AsyncMock(side_effect=RuntimeError("network error"))), \
             patch.object(HepsiburadaConnector, "search", new=AsyncMock(return_value=[])):
            connector = GenericConnector()
            results = await connector.search("test", None, None)
        assert results == []


class TestIngestPipeline:
    @pytest.mark.asyncio
    async def test_ingest_creates_product_and_offer(self, db: AsyncSession):
        batch = [{
            "name": "Samsung Galaxy A55 5G 256 GB",
            "brand": "Samsung",
            "price": "14999.99",
            "currency": "TRY",
            "url": "https://www.trendyol.com/samsung/galaxy-a55-p-1",
            "sellerName": "Samsung Türkiye",
            "imageUrl": "https://cdn.dsmcdn.com/image.jpg",
        }]
        summary = await ingest_batch(db, batch, "trendyol")
        assert summary["created"] == 1
        assert summary["errors"] == 0

        # Verify DB state
        from sqlalchemy import select
        products = (await db.execute(select(Product))).scalars().all()
        assert len(products) == 1
        assert products[0].name == "Samsung Galaxy A55 5G 256 GB"
        assert products[0].brand == "Samsung"

        offers = (await db.execute(select(MerchantOffer))).scalars().all()
        assert len(offers) == 1
        assert offers[0].merchant == "trendyol"
        assert offers[0].effective_price == Decimal("14999.99")

    @pytest.mark.asyncio
    async def test_ingest_records_initial_price_history(self, db: AsyncSession):
        batch = [{"name": "Test Product", "price": "1234.56", "currency": "TRY"}]
        await ingest_batch(db, batch, "trendyol")

        from sqlalchemy import select
        history = (await db.execute(select(PriceHistory))).scalars().all()
        assert len(history) == 1
        assert history[0].price == Decimal("1234.56")
        assert history[0].merchant == "trendyol"

    @pytest.mark.asyncio
    async def test_ingest_records_price_change_in_history(self, db: AsyncSession):
        # First ingest: price 1000
        await ingest_batch(db, [{"name": "Test Product", "price": "1000.00"}], "trendyol")
        # Second ingest: price changes to 900
        await ingest_batch(db, [{"name": "Test Product", "price": "900.00"}], "trendyol")

        from sqlalchemy import select
        history = (await db.execute(select(PriceHistory).order_by(PriceHistory.id))).scalars().all()
        assert len(history) == 2
        assert history[0].price == Decimal("1000.00")
        assert history[1].price == Decimal("900.00")

    @pytest.mark.asyncio
    async def test_ingest_no_duplicate_history_on_same_price(self, db: AsyncSession):
        # Ingest twice with same price
        await ingest_batch(db, [{"name": "Test Product", "price": "1000.00"}], "trendyol")
        await ingest_batch(db, [{"name": "Test Product", "price": "1000.00"}], "trendyol")

        from sqlalchemy import select
        history = (await db.execute(select(PriceHistory))).scalars().all()
        assert len(history) == 1  # No duplicate

    @pytest.mark.asyncio
    async def test_ingest_dedup_by_normalized_name(self, db: AsyncSession):
        """Same product ingested twice → 1 product, 1 offer (updated)."""
        batch = [{"name": "Samsung Galaxy A55", "price": "14999.00"}]
        await ingest_batch(db, batch, "trendyol")
        await ingest_batch(db, batch, "trendyol")

        from sqlalchemy import select
        count = (await db.execute(select(Product))).scalars().all()
        assert len(count) == 1


class TestCatalogSearch:
    @pytest.mark.asyncio
    async def test_search_finds_ingested_products(self, db: AsyncSession):
        await ingest_batch(db, [
            {"name": "iPhone 15 Pro 256GB", "brand": "Apple", "price": "49999.00"},
            {"name": "Samsung Galaxy S24", "brand": "Samsung", "price": "35999.00"},
        ], "trendyol")

        result = await search_products(db, "iphone", None, None, 1, 20)
        assert result["total"] == 1
        assert result["items"][0].name == "iPhone 15 Pro 256GB"

    @pytest.mark.asyncio
    async def test_search_by_brand(self, db: AsyncSession):
        await ingest_batch(db, [
            {"name": "iPhone 15", "brand": "Apple", "price": "44999.00"},
            {"name": "Galaxy S24", "brand": "Samsung", "price": "35999.00"},
        ], "trendyol")

        result = await search_products(db, None, None, "apple", 1, 20)
        assert result["total"] == 1
        assert result["items"][0].brand == "Apple"


class TestLiveSearchAndSeed:
    @pytest.mark.asyncio
    async def test_live_search_seeds_db_and_returns_products(self, db: AsyncSession):
        """Full pipeline: mock connector → ingest → DB query → results."""
        from app.catalog.live import live_search_and_seed

        mock_results = [
            {
                "title": "Xiaomi Redmi Note 13 Pro 256GB",
                "normalized_title": "xiaomi redmi note 13 pro 256gb",
                "price": Decimal("12999.00"),
                "currency": "TRY",
                "url": "https://www.trendyol.com/xiaomi/redmi-note-13-pro-p-1",
                "seller": "Xiaomi Türkiye",
                "merchant": "trendyol",
                "image_url": None,
                "product_url": "https://www.trendyol.com/xiaomi/redmi-note-13-pro-p-1",
            }
        ]

        with patch.dict("app.merchants.connector._CONNECTORS", {
            "trendyol": AsyncMock(search=AsyncMock(return_value=mock_results)),
        }):
            result = await live_search_and_seed(db, "xiaomi redmi", None, 1, 20)

        assert result["total"] == 1
        assert result["items"][0].name == "Xiaomi Redmi Note 13 Pro 256GB"

        # Price history was recorded
        from sqlalchemy import select
        history = (await db.execute(select(PriceHistory))).scalars().all()
        assert len(history) == 1
        assert history[0].price == Decimal("12999.00")

    @pytest.mark.asyncio
    async def test_live_search_empty_when_connectors_fail(self, db: AsyncSession):
        from app.catalog.live import live_search_and_seed

        with patch.dict("app.merchants.connector._CONNECTORS", {
            "trendyol": AsyncMock(search=AsyncMock(return_value=[])),
            "hepsiburada": AsyncMock(search=AsyncMock(return_value=[])),
        }):
            result = await live_search_and_seed(db, "nonexistent query xyz", None, 1, 20)

        assert result["total"] == 0
        assert result["items"] == []
