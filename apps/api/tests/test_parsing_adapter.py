"""Tests for parsing adapter response parser."""
import pytest
from app.parsing.adapter import _parse_response


def test_parse_valid_json():
    raw = '{"merchant": "Trendyol", "purchase_price": 1299.99, "currency": "TRY", "confidence": 0.95}'
    result = _parse_response(raw)
    assert result.merchant == "Trendyol"
    assert float(result.purchase_price) == pytest.approx(1299.99)
    assert result.confidence == 0.95


def test_parse_markdown_wrapped_json():
    raw = '```json\n{"merchant": "Hepsiburada", "confidence": 0.8}\n```'
    result = _parse_response(raw)
    assert result.merchant == "Hepsiburada"


def test_parse_invalid_returns_zero_confidence():
    result = _parse_response("not json at all")
    assert result.confidence == 0.0


def test_parse_partial_fields():
    raw = '{"product_title_raw": "Samsung TV 55\\"", "confidence": 0.7}'
    result = _parse_response(raw)
    assert "Samsung" in result.product_title_raw
