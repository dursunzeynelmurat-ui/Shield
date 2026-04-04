"""Tests for matching scoring logic."""
import pytest
from decimal import Decimal
from app.matching.service import _score_candidate, _tokenize
from app.models import Order


def _make_order(**kwargs) -> Order:
    order = Order.__new__(Order)
    defaults = dict(
        normalized_title="apple iphone 15 pro 256gb siyah",
        product_title_raw="Apple iPhone 15 Pro 256GB Siyah",
        brand="apple",
        model="iphone 15 pro",
        variant="256gb siyah",
        purchase_price=Decimal("45000"),
        seller_name="Apple Authorized",
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(order, k, v)
    return order


def test_tokenize_basic():
    tokens = _tokenize("apple iphone 15 pro")
    assert "apple" in tokens
    assert "iphone" in tokens
    assert "pro" in tokens


def test_score_perfect_match():
    order = _make_order()
    candidate = {
        "title": "apple iphone 15 pro 256gb siyah",
        "seller": "Apple Authorized",
        "price": 44000,
        "url": "https://example.com",
    }
    score = _score_candidate(order, candidate)
    assert score > 0.8


def test_score_irrelevant_candidate():
    order = _make_order()
    candidate = {
        "title": "samsung galaxy s24 128gb beyaz",
        "seller": "Samsung Store",
        "price": 30000,
        "url": "https://example.com",
    }
    score = _score_candidate(order, candidate)
    assert score < 0.4


def test_score_empty_title():
    order = _make_order(normalized_title=None, product_title_raw=None)
    score = _score_candidate(order, {"title": "anything", "price": None})
    assert score == 0.0
