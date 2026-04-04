"""Tests for recommendation business logic."""
import pytest
from datetime import date, timedelta
from app.actions.service import _determine_action
from app.models import ActionType, Order, ProductMatch


def _make_order(return_deadline=None) -> Order:
    o = Order.__new__(Order)
    o.return_deadline = return_deadline
    o.merchant = "trendyol"
    return o


def _make_match(same_variant=True, same_seller=False) -> ProductMatch:
    m = ProductMatch.__new__(ProductMatch)
    m.same_variant_verified = same_variant
    m.same_seller_verified = same_seller
    m.matched_url = "https://trendyol.com/product"
    return m


def test_within_window_same_seller_asks_price_match():
    order = _make_order(return_deadline=date.today() + timedelta(days=5))
    match = _make_match(same_variant=True, same_seller=True)
    action, _ = _determine_action(order, match)
    assert action == ActionType.ask_price_match


def test_within_window_different_seller_return_and_rebuy():
    order = _make_order(return_deadline=date.today() + timedelta(days=5))
    match = _make_match(same_variant=True, same_seller=False)
    action, _ = _determine_action(order, match)
    assert action == ActionType.return_and_rebuy


def test_expired_window_manual_review():
    order = _make_order(return_deadline=date.today() - timedelta(days=1))
    match = _make_match(same_variant=True, same_seller=True)
    action, _ = _determine_action(order, match)
    assert action == ActionType.manual_review


def test_no_match_manual_review():
    order = _make_order(return_deadline=date.today() + timedelta(days=5))
    action, _ = _determine_action(order, None)
    assert action == ActionType.manual_review
