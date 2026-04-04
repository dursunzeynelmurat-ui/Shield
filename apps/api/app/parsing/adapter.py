"""AI provider adapter interface for parsing order screenshots."""
import base64
import json
from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas import ParsedOrderData


EXTRACTION_PROMPT = """You are an order extraction assistant. Extract purchase information from this e-commerce order screenshot or invoice.

Return a JSON object with these fields (use null if not found):
{
  "merchant": "store name",
  "merchant_order_no": "order number",
  "product_title_raw": "full product name as shown",
  "brand": "brand name if identifiable",
  "model": "model name/number if identifiable",
  "variant": "color/size/config variant if shown",
  "sku": "SKU or product code if shown",
  "seller_name": "seller name (may differ from merchant)",
  "purchase_price": 123.45,
  "currency": "TRY",
  "purchased_at": "YYYY-MM-DD",
  "delivery_date": "YYYY-MM-DD or null",
  "return_deadline": "YYYY-MM-DD or null",
  "confidence": 0.0-1.0
}

Respond ONLY with the JSON object, no markdown, no explanation."""


class BaseParsingAdapter(ABC):
    @abstractmethod
    async def parse_image(self, image_path: Path) -> ParsedOrderData:
        pass


class OpenAIParsingAdapter(BaseParsingAdapter):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def parse_image(self, image_path: Path) -> ParsedOrderData:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)

        image_bytes = image_path.read_bytes()
        b64 = base64.b64encode(image_bytes).decode()
        ext = image_path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
            max_tokens=1000,
        )
        raw_text = response.choices[0].message.content or "{}"
        return _parse_response(raw_text)


class AnthropicParsingAdapter(BaseParsingAdapter):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def parse_image(self, image_path: Path) -> ParsedOrderData:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        image_bytes = image_path.read_bytes()
        b64 = base64.b64encode(image_bytes).decode()
        ext = image_path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

        response = await client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
        )
        raw_text = response.content[0].text if response.content else "{}"
        return _parse_response(raw_text)


class StubParsingAdapter(BaseParsingAdapter):
    """Stub used when no AI key is configured. Returns low-confidence placeholder."""

    async def parse_image(self, image_path: Path) -> ParsedOrderData:
        return ParsedOrderData(
            product_title_raw="[Stub] Product extracted from upload",
            merchant="Unknown",
            purchase_price=None,
            currency="TRY",
            confidence=0.1,
            raw_extraction={"note": "No AI provider configured — stub result"},
        )


def _parse_response(raw_text: str) -> ParsedOrderData:
    try:
        # Strip markdown fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        data = json.loads(text)
        return ParsedOrderData(**{k: v for k, v in data.items() if k in ParsedOrderData.model_fields})
    except Exception:
        return ParsedOrderData(confidence=0.0, raw_extraction={"raw": raw_text})


def get_parsing_adapter() -> BaseParsingAdapter:
    from app.config import settings

    if settings.ai_provider == "openai" and settings.openai_api_key:
        return OpenAIParsingAdapter(settings.openai_api_key, settings.openai_model)
    elif settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicParsingAdapter(settings.anthropic_api_key, settings.anthropic_model)
    return StubParsingAdapter()
