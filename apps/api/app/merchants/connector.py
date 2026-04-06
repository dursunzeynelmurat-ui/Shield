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

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

# Turkish character normalization table (22 chars)
_TR_TABLE = str.maketrans("ğüşıöçĞÜŞİÖÇ", "gusiocGUSIOC")


def _normalize_title(title: str) -> str:
    """Lowercase + Turkish transliteration + collapse whitespace."""
    t = title.translate(_TR_TABLE).lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(t.split())

# ---------------------------------------------------------------------------
# Shared HTTP client settings
# ---------------------------------------------------------------------------

_TIMEOUT = httpx.Timeout(connect=8.0, read=15.0, write=5.0, pool=5.0)
_MAX_RETRIES = 2
_RETRY_STATUSES = frozenset([429, 500, 502, 503, 504])

# Full browser-like headers including sec-* fields required by modern CDN/bot checks
_HEADERS_TR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.trendyol.com/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}

_HEADERS_HB = {
    **_HEADERS_TR,
    "Referer": "https://www.hepsiburada.com/",
    "Sec-Fetch-Site": "same-origin",
}


async def _fetch_html(url: str, headers: dict) -> httpx.Response | None:
    """GET with retry on transient errors. Returns None on permanent failure."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=_TIMEOUT,
                follow_redirects=True,
                http2=True,
            ) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                return resp
            if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES:
                delay = 2.0 ** attempt
                logger.debug("HTTP %s for %s, retrying in %.1fs", resp.status_code, url, delay)
                await asyncio.sleep(delay)
                continue
            logger.warning("HTTP %s fetching %s", resp.status_code, url)
            return None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(2.0 ** attempt)
    if last_exc:
        logger.warning("Fetch failed for %s: %s", url, last_exc)
    return None


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
            api_resp = await _fetch_html(
                _TY_API_SEARCH.format(q=encoded),
                {**_HEADERS_TR, "Accept": "application/json", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"},
            )
            if api_resp is not None:
                results = self._parse_api_results(api_resp.json())
                if results:
                    logger.info("Trendyol API search: %d results for %r", len(results), query)
                    return results
        except Exception as exc:
            logger.debug("Trendyol API search failed: %s", exc)

        # Fallback: scrape the HTML search results page
        html_resp = await _fetch_html(_TY_SEARCH.format(q=encoded), _HEADERS_TR)
        if html_resp is not None:
            results = self._parse_html_results(html_resp.text)
            if results:
                logger.info("Trendyol HTML search: %d results for %r", len(results), query)
                return results
            logger.warning("Trendyol HTML search: 0 results for %r (page len=%d)", query, len(html_resp.text))
        return []

    def _parse_api_results(self, data: dict) -> list[dict]:
        products = (
            data.get("result", {}).get("products")
            or data.get("products")
            or []
        )
        return [r for r in (self._map_product(p) for p in products[:10]) if r]

    def _parse_html_results(self, html: str) -> list[dict]:
        """Parse product cards from Trendyol search HTML."""
        products: list[dict] = []

        # Primary: __SEARCH_APP_INITIAL_STATE__ JSON blob
        m = re.search(
            r'window\.__SEARCH_APP_INITIAL_STATE__\s*=\s*({.+?});\s*(?:window\.|</script>)',
            html, re.DOTALL,
        )
        if m:
            try:
                state = json.loads(m.group(1))
                products = (
                    state.get("products")
                    or state.get("result", {}).get("products")
                    or []
                )
            except json.JSONDecodeError:
                pass

        # Fallback: bare "products" array in any script block
        if not products:
            m2 = re.search(r'"products"\s*:\s*(\[.+?\])\s*,\s*"[a-z]', html, re.DOTALL)
            if m2:
                try:
                    products = json.loads(m2.group(1))
                except json.JSONDecodeError:
                    pass

        return [r for r in (self._map_product(p) for p in products[:10]) if r]

    def _map_product(self, p: dict) -> dict | None:
        """Map a raw Trendyol product dict to canonical connector output."""
        title = p.get("name") or p.get("title") or ""
        if not title:
            return None
        url = p.get("url") or ""
        if url and not url.startswith("http"):
            url = f"https://www.trendyol.com{url}"
        price_obj = p.get("price") or {}
        price = _to_decimal(
            price_obj.get("discountedPrice")
            or price_obj.get("sellingPrice")
            or p.get("priceInfo", {}).get("discountedPrice")
            or p.get("priceInfo", {}).get("price")
        )
        return {
            "url": url,
            "product_url": url,
            "title": title,
            "normalized_title": _normalize_title(title),
            "seller": p.get("merchantName") or p.get("seller") or "Trendyol",
            "price": price,
            "currency": "TRY",
            "image_url": p.get("imageUrl") or (p.get("images") or [None])[0],
            "merchant": self.merchant_name,
        }

    # ------------------------------------------------------------------
    async def fetch_price(self, url: str) -> dict:
        if not url or "trendyol.com" not in url:
            return _failed("URL is not a Trendyol product URL")
        resp = await _fetch_html(url, _HEADERS_TR)
        if resp is None:
            return _failed("Request failed after retries")
        return self._parse_product_page(resp.text, url)

    async def fetch_deals(self) -> list[dict]:
        """Scrape Trendyol campaign/coupon page for active offers."""
        url = "https://www.trendyol.com/kampanya/indirim-kuponlari"
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_TR, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return []
            html = resp.text
            deals: list[dict] = []
            # Try __NEXT_DATA__ / __REDUX_STATE__ embedded JSON
            m = re.search(r'window\.__REDUX_STATE__\s*=\s*({.+?});\s*</script>', html, re.DOTALL)
            if m:
                try:
                    state = json.loads(m.group(1))
                    coupons = (
                        state.get("coupons", {}).get("data") or
                        state.get("campaigns", {}).get("data") or
                        []
                    )
                    for c in coupons[:20]:
                        deals.append({
                            "title": c.get("title") or c.get("name") or "Trendyol Kuponu",
                            "code": c.get("code"),
                            "discount_type": "percentage" if c.get("discountType") == "PERCENT" else "fixed_amount",
                            "discount_value": c.get("discountValue") or c.get("discount"),
                            "minimum_spend": c.get("minimumOrderAmount"),
                            "conditions": c.get("description"),
                            "url": c.get("deeplink") or url,
                            "expires_at": c.get("expiryDate"),
                        })
                    if deals:
                        return deals
                except (json.JSONDecodeError, KeyError):
                    pass
            # Fallback: regex scan for coupon codes in page
            codes = re.findall(r'"code"\s*:\s*"([A-Z0-9]{4,20})"', html)
            for code in codes[:10]:
                deals.append({
                    "title": f"Trendyol {code} Kuponu",
                    "code": code,
                    "discount_type": None,
                    "discount_value": None,
                    "minimum_spend": None,
                    "conditions": None,
                    "url": url,
                    "expires_at": None,
                })
            return deals
        except Exception as exc:
            logger.warning("TrendyolConnector.fetch_deals error: %s", exc)
            return []

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
        resp = await _fetch_html(_HB_SEARCH.format(q=encoded), _HEADERS_HB)
        if resp is None:
            return []
        results = self._parse_search(resp.text)
        if results:
            logger.info("Hepsiburada search: %d results for %r", len(results), query)
        else:
            logger.warning("Hepsiburada search: 0 results for %r (page len=%d)", query, len(resp.text))
        return results

    def _parse_search(self, html: str) -> list[dict]:
        # Strategy 1: __NEXT_DATA__ JSON blob
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.+?)</script>', html, re.DOTALL)
        if m:
            try:
                next_data = json.loads(m.group(1))
                page_props = next_data.get("props", {}).get("pageProps", {})
                products = (
                    page_props.get("products")
                    or page_props.get("initialState", {})
                       .get("products", {})
                       .get("productList", {})
                       .get("products")
                    or []
                )
                if products:
                    return [r for r in (self._map_product(p) for p in products[:10]) if r]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.debug("HB __NEXT_DATA__ parse failed: %s", exc)

        # Strategy 2: data-sku-id attributes (older page format)
        results: list[dict] = []
        for m2 in re.finditer(
            r'data-sku-id="([^"]+)"[^>]*>.*?data-bind="[^"]*text:\s*name[^"]*"[^>]*>([^<]+)',
            html, re.DOTALL,
        ):
            sku, name = m2.group(1), m2.group(2).strip()
            if not name:
                continue
            url = f"https://www.hepsiburada.com/-p-{sku}"
            results.append({
                "url": url,
                "product_url": url,
                "title": name,
                "normalized_title": _normalize_title(name),
                "seller": "Hepsiburada",
                "price": None,
                "currency": "TRY",
                "image_url": None,
                "merchant": self.merchant_name,
            })
            if len(results) >= 10:
                break

        return results

    def _map_product(self, p: dict) -> dict | None:
        """Map a raw Hepsiburada product dict to canonical connector output."""
        title = p.get("name") or p.get("title") or ""
        if not title:
            return None
        url = p.get("url") or p.get("productGroupId") or ""
        if url and not url.startswith("http"):
            url = f"https://www.hepsiburada.com/{url}"
        price = _to_decimal(
            p.get("price") or p.get("salePrice") or p.get("discountedPrice")
        )
        return {
            "url": url,
            "product_url": url,
            "title": title,
            "normalized_title": _normalize_title(title),
            "seller": p.get("merchantName") or p.get("seller") or "Hepsiburada",
            "price": price,
            "currency": "TRY",
            "image_url": p.get("imageUrl") or (p.get("images") or [None])[0],
            "merchant": self.merchant_name,
        }

    # ------------------------------------------------------------------
    async def fetch_price(self, url: str) -> dict:
        if not url or "hepsiburada.com" not in url:
            return _failed("URL is not a Hepsiburada product URL")
        resp = await _fetch_html(url, _HEADERS_HB)
        if resp is None:
            return _failed("Request failed after retries")
        return self._parse_product_page(resp.text)

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

    async def fetch_deals(self) -> list[dict]:
        """Scrape Hepsiburada campaign page for active coupon offers."""
        url = "https://www.hepsiburada.com/indirim-kuponlari"
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS_TR, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return []
            html = resp.text
            deals: list[dict] = []
            # Try __NEXT_DATA__
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>({.+?})</script>', html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    coupons = (
                        data.get("props", {}).get("pageProps", {}).get("coupons") or
                        data.get("props", {}).get("pageProps", {}).get("campaigns") or
                        []
                    )
                    for c in coupons[:20]:
                        deals.append({
                            "title": c.get("title") or c.get("name") or "Hepsiburada Kuponu",
                            "code": c.get("couponCode") or c.get("code"),
                            "discount_type": "percentage" if "%" in str(c.get("title", "")) else "fixed_amount",
                            "discount_value": c.get("discountValue") or c.get("discountRate"),
                            "minimum_spend": c.get("minimumCartPrice") or c.get("minOrderAmount"),
                            "conditions": c.get("description"),
                            "url": c.get("url") or url,
                            "expires_at": c.get("endDate") or c.get("expiryDate"),
                        })
                    if deals:
                        return deals
                except (json.JSONDecodeError, KeyError):
                    pass
            # Fallback: regex scan
            codes = re.findall(r'"couponCode"\s*:\s*"([A-Z0-9]{4,20})"', html)
            for code in codes[:10]:
                deals.append({
                    "title": f"Hepsiburada {code} Kuponu",
                    "code": code,
                    "discount_type": None,
                    "discount_value": None,
                    "minimum_spend": None,
                    "conditions": None,
                    "url": url,
                    "expires_at": None,
                })
            return deals
        except Exception as exc:
            logger.warning("HepsiburadaConnector.fetch_deals error: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Generic connector (n11, amazon.com.tr, etc.)
# ---------------------------------------------------------------------------

class GenericConnector(BaseConnector):
    """
    Cross-merchant fallback: aggregates results from all registered connectors.
    Used when the merchant on an order does not match any specific connector.
    """
    merchant_name = "generic"
    domain = ""

    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        """Search all registered connectors in parallel and merge results."""
        if not _CONNECTORS:
            return []
        tasks = [conn.search(title, brand, model) for conn in _CONNECTORS.values()]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[dict] = []
        for results in all_results:
            if isinstance(results, list):
                merged.extend(results)
        # Deduplicate by normalized_title, keep first occurrence
        seen: set[str] = set()
        deduped: list[dict] = []
        for r in merged:
            key = r.get("normalized_title") or r.get("title", "")
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)
        logger.info("GenericConnector aggregated %d results", len(deduped))
        return deduped[:10]

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

# Public alias used by background tasks
CONNECTOR_REGISTRY: dict[str, BaseConnector] = _CONNECTORS


def get_connector(merchant: str | None) -> BaseConnector:
    if merchant:
        key = merchant.lower().replace(" ", "").replace(".", "")
        for name, connector in _CONNECTORS.items():
            if name in key or key in name:
                return connector
    return GenericConnector()
