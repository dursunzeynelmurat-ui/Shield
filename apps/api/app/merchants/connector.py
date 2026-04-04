"""Merchant connector pattern — each merchant implements BaseConnector."""
from abc import ABC, abstractmethod


class BaseConnector(ABC):
    merchant_name: str
    domain: str

    @abstractmethod
    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        """Return list of candidates: [{url, title, seller, price}]"""
        pass

    @abstractmethod
    async def fetch_price(self, url: str) -> dict:
        """Return price data: {listed_price, shipping_price, final_price, currency, seller, stock_status}"""
        pass


class TrendyolConnector(BaseConnector):
    merchant_name = "trendyol"
    domain = "trendyol.com"

    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        query = " ".join(filter(None, [brand, model, title]))[:100]
        # Real implementation would call Trendyol search API or scrape
        # Stub: return empty for now
        return []

    async def fetch_price(self, url: str) -> dict:
        # Real implementation uses Playwright / structured extraction
        return {
            "listed_price": None,
            "shipping_price": None,
            "final_price": None,
            "currency": "TRY",
            "seller": None,
            "stock_status": "unknown",
            "success": False,
            "error_message": "Connector not fully implemented",
        }


class HepsiburadaConnector(BaseConnector):
    merchant_name = "hepsiburada"
    domain = "hepsiburada.com"

    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        return []

    async def fetch_price(self, url: str) -> dict:
        return {
            "listed_price": None, "shipping_price": None, "final_price": None,
            "currency": "TRY", "seller": None, "stock_status": "unknown",
            "success": False, "error_message": "Connector not fully implemented",
        }


class GenericConnector(BaseConnector):
    merchant_name = "generic"
    domain = ""

    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        return []

    async def fetch_price(self, url: str) -> dict:
        return {
            "listed_price": None, "shipping_price": None, "final_price": None,
            "currency": "TRY", "seller": None, "stock_status": "unknown",
            "success": False, "error_message": "Generic connector — no scraping",
        }


_CONNECTORS: dict[str, BaseConnector] = {
    "trendyol": TrendyolConnector(),
    "hepsiburada": HepsiburadaConnector(),
}


def get_connector(merchant: str | None) -> BaseConnector:
    if merchant:
        key = merchant.lower().replace(" ", "")
        for name, connector in _CONNECTORS.items():
            if name in key:
                return connector
    return GenericConnector()
