"""
Merchant connector pattern
===========================
Each merchant implements BaseConnector.  Connectors are responsible for:

  1. search()     — find product candidates matching an order's title/brand/model
  2. fetch_price() — fetch current price data for a known product URL
  3. fetch_deals() — optional: return current coupon/offer data

Implementations use httpx (already a project dependency) with browser-like
headers to avoid trivial bot-rejection.  All network calls have a hard 15s
timeout and return gracefully on error so the pipeline is never blocked.

Scraping strategy
-----------------
Both Trendyol and Hepsiburada embed structured JSON into their HTML pages.
- Trendyol: embeds ``window.__PRODUCT_DETAIL_APP_INITIAL_STATE__`` and
  search results in a ``<script>`` tag as JSON.
- Hepsiburada: embeds a ``<script type="application/ld+json">`` JSON-LD block
  on product pages; search results are in a ``data-sku-id`` grid.

No external parsing library (BeautifulSoup, lxml) is required — we use
``re.search`` on the raw HTML since the target patterns are predictable.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP client settings
# ---------------------------------------------------------------------------

_TIMEOUT = httpx.Timeout(connect=5.0, read=12.0, write=5.0, pool=5.0)

# Rotate a minimal set of headers that look like a real browser
_HEADERS_TR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.trendyol.com/",
}

_HEADERS_HB = {
    **_HEADERS_TR,
    "Referer": "https://www.hepsiburada.com/",
}


def _to_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return None


def _extract_json_var(html: str, var_name: str) -> dict | list | None:
    """Extract a JS variable assignment ``var_name = {...}`` from page HTML."""
    pattern = re.compile(
        re.escape(var_name) + r"\s*=\s*(\{.*?\});",
        re.DOTALL,
    )
    m = pattern.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _extract_jsonld(html: str) -> dict | None:
    """Extract the first ``<script type="application/ld+json">`` block."""
    m = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        if isinstance(data, list):
            data = data[0]
        return data
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseConnector(ABC):
    merchant_name: str
    domain: str

    @abstractmethod
    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        """
        Return up to 10 candidate products as dicts:
          [{url, title, seller, price, currency, image_url}]
        """

    @abstractmethod
    async def fetch_price(self, url: str) -> dict:
        """
        Return current price data:
          {listed_price, shipping_price, final_price, currency,
           seller, stock_status, success, error_message}
        """

    async def fetch_deals(self) -> list[dict]:
        """
        Optional: return active coupon/offer dicts:
          [{title, code, discount_type, discount_value, minimum_spend,
            conditions, url, expires_at}]
        Default: empty list (opt-in per connector).
        """
        return []


# ---------------------------------------------------------------------------
# Trendyol
# ---------------------------------------------------------------------------

_TY_SEARCH = "https://www.trendyol.com/sr?q={q}&qt={q}&st={q}&os=1"
_TY_API_SEARCH = (
    "https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/"
    "infinite-scroll/sr?q={q}&qt={q}&st={q}&os=1&pi=1&psize=10"
)


class TrendyolConnector(BaseConnector):
    merchant_name = "trendyol"
    domain = "trendyol.com"

    # ------------------------------------------------------------------
    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        query = " ".join(filter(None, [brand, model, title]))[:120]
        encoded = quote_plus(query)

        # Try the internal search API first (returns JSON directly)
        try:
            async with httpx.AsyncClient(
                headers={**_HEADERS_TR, "Accept": "application/json"},
                timeout=_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = await client.get(_TY_API_SEARCH.format(q=encoded))
                if resp.status_code == 200:
                    return self._parse_api_results(resp.json())
        except Exception as exc:
            logger.debug("Trendyol API search failed: %s", exc)

        # Fallback: scrape the HTML search results page
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_TR, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(_TY_SEARCH.format(q=encoded))
                if resp.status_code == 200:
                    return self._parse_html_results(resp.text)
        except Exception as exc:
            logger.warning("Trendyol HTML search failed: %s", exc)

        return []

    def _parse_api_results(self, data: dict) -> list[dict]:
        results = []
        products = (
            data.get("result", {}).get("products")
            or data.get("products")
            or []
        )
        for p in products[:10]:
            url = p.get("url") or ""
            if url and not url.startswith("http"):
                url = f"https://www.trendyol.com{url}"
            results.append({
                "url": url,
                "title": p.get("name") or p.get("title") or "",
                "seller": p.get("merchantName") or p.get("seller") or "Trendyol",
                "price": _to_decimal(p.get("price", {}).get("discountedPrice") or p.get("price", {}).get("sellingPrice")),
                "currency": "TRY",
                "image_url": p.get("imageUrl") or (p.get("images") or [None])[0],
            })
        return results

    def _parse_html_results(self, html: str) -> list[dict]:
        """Parse product cards from Trendyol search HTML."""
        results: list[dict] = []

        # Trendyol embeds all search state as JSON in a script tag
        m = re.search(r'window\.__SEARCH_APP_INITIAL_STATE__\s*=\s*({.+?});\s*</script>', html, re.DOTALL)
        if not m:
            # Try alternate pattern
            m = re.search(r'"products"\s*:\s*(\[.+?\])\s*,\s*"[a-z]', html, re.DOTALL)
            if not m:
                return []
            try:
                products = json.loads(m.group(1))
            except json.JSONDecodeError:
                return []
        else:
            try:
                state = json.loads(m.group(1))
                products = state.get("products") or state.get("result", {}).get("products") or []
            except json.JSONDecodeError:
                return []

        for p in products[:10]:
            url = p.get("url") or ""
            if url and not url.startswith("http"):
                url = f"https://www.trendyol.com{url}"
            results.append({
                "url": url,
                "title": p.get("name") or p.get("title") or "",
                "seller": p.get("merchantName") or "Trendyol",
                "price": _to_decimal(
                    (p.get("price") or {}).get("discountedPrice")
                    or (p.get("price") or {}).get("sellingPrice")
                    or p.get("priceInfo", {}).get("discountedPrice")
                ),
                "currency": "TRY",
                "image_url": p.get("imageUrl"),
            })
        return results

    # ------------------------------------------------------------------
    async def fetch_price(self, url: str) -> dict:
        if not url or "trendyol.com" not in url:
            return _failed("URL is not a Trendyol product URL")
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_TR, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return _failed(f"HTTP {resp.status_code}")
            return self._parse_product_page(resp.text, url)
        except httpx.TimeoutException:
            return _failed("Request timed out")
        except Exception as exc:
            logger.warning("Trendyol fetch_price error: %s", exc)
            return _failed(str(exc))

    def _parse_product_page(self, html: str, url: str) -> dict:
        # Strategy 1: __PRODUCT_DETAIL_APP_INITIAL_STATE__
        m = re.search(
            r'window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.+?});\s*(?:window|</script>)',
            html, re.DOTALL,
        )
        if m:
            try:
                state = json.loads(m.group(1))
                product = state.get("product") or {}
                price_info = product.get("priceInfo") or {}
                listed = _to_decimal(price_info.get("price") or price_info.get("originalPrice"))
                final = _to_decimal(price_info.get("discountedPrice") or price_info.get("price"))
                seller = (product.get("merchant") or {}).get("name") or "Trendyol"
                in_stock = product.get("hasStock", True)
                return {
                    "listed_price": listed,
                    "shipping_price": Decimal("0"),
                    "final_price": final or listed,
                    "currency": "TRY",
                    "seller": seller,
                    "stock_status": "in_stock" if in_stock else "out_of_stock",
                    "success": (final or listed) is not None,
                    "error_message": None,
                }
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # Strategy 2: JSON-LD
        ld = _extract_jsonld(html)
        if ld and ld.get("@type") in ("Product", "product"):
            offers = ld.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = _to_decimal(offers.get("price") or offers.get("lowPrice"))
            return {
                "listed_price": price,
                "shipping_price": None,
                "final_price": price,
                "currency": offers.get("priceCurrency", "TRY"),
                "seller": (ld.get("seller") or {}).get("name") or "Trendyol",
                "stock_status": "in_stock" if offers.get("availability", "").endswith("InStock") else "unknown",
                "success": price is not None,
                "error_message": None,
            }

        # Strategy 3: inline price regex
        m2 = re.search(r'"discountedPrice"\s*:\s*([\d.]+)', html)
        if m2:
            price = _to_decimal(m2.group(1))
            return {
                "listed_price": price,
                "shipping_price": Decimal("0"),
                "final_price": price,
                "currency": "TRY",
                "seller": "Trendyol",
                "stock_status": "unknown",
                "success": price is not None,
                "error_message": None,
            }

        return _failed("Could not extract price from page")


# ---------------------------------------------------------------------------
# Hepsiburada
# ---------------------------------------------------------------------------

_HB_SEARCH = "https://www.hepsiburada.com/ara?q={q}&showSearchResult=true"


class HepsiburadaConnector(BaseConnector):
    merchant_name = "hepsiburada"
    domain = "hepsiburada.com"

    # ------------------------------------------------------------------
    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        query = " ".join(filter(None, [brand, model, title]))[:120]
        encoded = quote_plus(query)
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_HB, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(_HB_SEARCH.format(q=encoded))
            if resp.status_code != 200:
                return []
            return self._parse_search(resp.text)
        except Exception as exc:
            logger.warning("Hepsiburada search error: %s", exc)
            return []

    def _parse_search(self, html: str) -> list[dict]:
        results: list[dict] = []

        # Hepsiburada embeds product data as JSON in a <script id="__NEXT_DATA__"> tag
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.+?)</script>', html, re.DOTALL)
        if m:
            try:
                next_data = json.loads(m.group(1))
                page_props = next_data.get("props", {}).get("pageProps", {})
                # Products can be at different paths depending on page type
                products = (
                    page_props.get("products")
                    or page_props.get("initialState", {}).get("products", {}).get("productList", {}).get("products")
                    or []
                )
                for p in products[:10]:
                    url = p.get("url") or p.get("productGroupId") or ""
                    if url and not url.startswith("http"):
                        url = f"https://www.hepsiburada.com/{url}"
                    results.append({
                        "url": url,
                        "title": p.get("name") or p.get("title") or "",
                        "seller": p.get("merchantName") or p.get("seller") or "Hepsiburada",
                        "price": _to_decimal(p.get("price") or p.get("salePrice") or p.get("discountedPrice")),
                        "currency": "TRY",
                        "image_url": p.get("imageUrl") or p.get("images", [None])[0],
                    })
                if results:
                    return results
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # Fallback: extract from data attributes in HTML
        # <li data-sku-id="..." data-listing-id="..." ...>
        for m2 in re.finditer(r'data-sku-id="([^"]+)"[^>]*data-listing-id="([^"]+)"', html):
            sku = m2.group(1)
            listing = m2.group(2)
            results.append({
                "url": f"https://www.hepsiburada.com/-p-{sku}",
                "title": listing,
                "seller": "Hepsiburada",
                "price": None,
                "currency": "TRY",
                "image_url": None,
            })
            if len(results) >= 10:
                break

        return results

    # ------------------------------------------------------------------
    async def fetch_price(self, url: str) -> dict:
        if not url or "hepsiburada.com" not in url:
            return _failed("URL is not a Hepsiburada product URL")
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_HB, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return _failed(f"HTTP {resp.status_code}")
            return self._parse_product_page(resp.text)
        except httpx.TimeoutException:
            return _failed("Request timed out")
        except Exception as exc:
            logger.warning("Hepsiburada fetch_price error: %s", exc)
            return _failed(str(exc))

    def _parse_product_page(self, html: str) -> dict:
        # Strategy 1: JSON-LD (most reliable on Hepsiburada)
        ld = _extract_jsonld(html)
        if ld:
            if isinstance(ld, list):
                ld = next((x for x in ld if x.get("@type") == "Product"), ld[0] if ld else {})
            if ld.get("@type") == "Product":
                offers = ld.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = _to_decimal(offers.get("price") or offers.get("lowPrice"))
                in_stock = "InStock" in (offers.get("availability") or "")
                return {
                    "listed_price": price,
                    "shipping_price": None,
                    "final_price": price,
                    "currency": offers.get("priceCurrency", "TRY"),
                    "seller": (ld.get("seller") or offers.get("seller") or {}).get("name") or "Hepsiburada",
                    "stock_status": "in_stock" if in_stock else "out_of_stock",
                    "success": price is not None,
                    "error_message": None,
                }

        # Strategy 2: __NEXT_DATA__
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.+?)</script>', html, re.DOTALL)
        if m:
            try:
                next_data = json.loads(m.group(1))
                product = (
                    next_data.get("props", {}).get("pageProps", {}).get("product")
                    or next_data.get("props", {}).get("pageProps", {})
                )
                price = _to_decimal(
                    product.get("price") or product.get("salePrice")
                    or product.get("discountedPrice")
                )
                if price:
                    return {
                        "listed_price": _to_decimal(product.get("originalPrice") or price),
                        "shipping_price": None,
                        "final_price": price,
                        "currency": "TRY",
                        "seller": product.get("merchantName") or "Hepsiburada",
                        "stock_status": "in_stock" if product.get("inStock", True) else "out_of_stock",
                        "success": True,
                        "error_message": None,
                    }
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # Strategy 3: regex on inline price
        m2 = re.search(r'"finalPrice"\s*:\s*([\d.]+)', html)
        if m2:
            price = _to_decimal(m2.group(1))
            return {
                "listed_price": price, "shipping_price": None, "final_price": price,
                "currency": "TRY", "seller": "Hepsiburada", "stock_status": "unknown",
                "success": price is not None, "error_message": None,
            }

        return _failed("Could not extract price from page")


# ---------------------------------------------------------------------------
# Generic connector (n11, amazon.com.tr, etc.)
# ---------------------------------------------------------------------------

class GenericConnector(BaseConnector):
    merchant_name = "generic"
    domain = ""

    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        return []

    async def fetch_price(self, url: str) -> dict:
        """Try JSON-LD extraction on any product URL as best-effort."""
        if not url:
            return _failed("No URL provided")
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_TR, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return _failed(f"HTTP {resp.status_code}")
            ld = _extract_jsonld(resp.text)
            if ld and ld.get("@type") == "Product":
                offers = ld.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = _to_decimal(offers.get("price"))
                return {
                    "listed_price": price, "shipping_price": None, "final_price": price,
                    "currency": offers.get("priceCurrency", "TRY"),
                    "seller": None, "stock_status": "unknown",
                    "success": price is not None, "error_message": None,
                }
        except Exception as exc:
            return _failed(str(exc))
        return _failed("No JSON-LD product data found")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _failed(msg: str) -> dict:
    return {
        "listed_price": None, "shipping_price": None, "final_price": None,
        "currency": "TRY", "seller": None, "stock_status": "unknown",
        "success": False, "error_message": msg,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_CONNECTORS: dict[str, BaseConnector] = {
    "trendyol": TrendyolConnector(),
    "hepsiburada": HepsiburadaConnector(),
}


def get_connector(merchant: str | None) -> BaseConnector:
    if merchant:
        key = merchant.lower().replace(" ", "").replace(".", "")
        for name, connector in _CONNECTORS.items():
            if name in key or key in name:
                return connector
    return GenericConnector()
