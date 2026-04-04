"""Product matching service."""
import re
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MatchMethod, Order, OrderStatus, ProductMatch
from app.merchants.connector import get_connector


async def match_product(order: Order, db: AsyncSession) -> ProductMatch:
    order.status = OrderStatus.matching
    await db.commit()

    connector = get_connector(order.merchant)
    candidates = await connector.search(
        title=order.normalized_title or order.product_title_raw or "",
        brand=order.brand,
        model=order.model,
    )

    best = None
    best_score = 0.0

    for candidate in candidates:
        score = _score_candidate(order, candidate)
        if score > best_score:
            best_score = score
            best = candidate

    if best is None:
        # Create a low-confidence placeholder so user can fill manually
        best = {"url": None, "title": order.product_title_raw, "seller": order.seller_name, "price": None}
        best_score = 0.0

    match = ProductMatch(
        order_id=order.id,
        canonical_title=best.get("title"),
        matched_url=best.get("url"),
        merchant=order.merchant,
        seller_name=best.get("seller"),
        match_method=MatchMethod.scrape_search,
        match_confidence=round(best_score, 3),
        same_variant_verified=best_score >= 0.8,
        same_seller_verified=False,
        is_active=True,
    )
    db.add(match)

    order.status = OrderStatus.matched
    await db.commit()
    await db.refresh(match)
    return match


def _score_candidate(order: Order, candidate: dict) -> float:
    score = 0.0
    title = (candidate.get("title") or "").lower()

    tokens_needed = _tokenize(order.normalized_title or order.product_title_raw or "")
    if not tokens_needed:
        return 0.0

    matched = sum(1 for t in tokens_needed if t in title)
    token_score = matched / len(tokens_needed)
    score += token_score * 0.5

    if order.brand and order.brand.lower() in title:
        score += 0.2

    if order.model and order.model.lower() in title:
        score += 0.2

    if order.variant and order.variant.lower() in title:
        score += 0.1

    # Price similarity
    candidate_price = candidate.get("price")
    if order.purchase_price and candidate_price:
        try:
            ratio = float(candidate_price) / float(order.purchase_price)
            if 0.5 <= ratio <= 2.0:
                score += 0.1 * (1 - abs(1 - ratio))
        except (TypeError, ZeroDivisionError):
            pass

    return min(score, 1.0)


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 2]
