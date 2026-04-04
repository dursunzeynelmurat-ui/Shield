"""Deterministic recommendation engine."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ActionRecommendation, ActionType, Alert, AlertType, Order,
    OrderStatus, ProductMatch,
)


async def generate_recommendation(order_id: int, db: AsyncSession) -> ActionRecommendation | None:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.product_matches),
            selectinload(Order.alerts),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        return None

    # Find latest price-drop alert
    price_alerts = sorted(
        [a for a in order.alerts if a.alert_type == AlertType.price_drop],
        key=lambda a: a.created_at,
        reverse=True,
    )
    if not price_alerts:
        return None

    latest_alert = price_alerts[0]
    active_matches = [m for m in order.product_matches if m.is_active]
    match = active_matches[0] if active_matches else None

    action_type, text = _determine_action(order, match)

    rec = ActionRecommendation(
        order_id=order_id,
        alert_id=latest_alert.id,
        action_type=action_type,
        recommended_text=text,
        target_url=match.matched_url if match else None,
        estimated_savings=latest_alert.amount_saved,
        confidence=0.9 if action_type != ActionType.manual_review else 0.5,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


def _determine_action(order: Order, match: ProductMatch | None) -> tuple[ActionType, str]:
    today = date.today()
    within_return_window = order.return_deadline and today <= order.return_deadline

    if not within_return_window:
        return (
            ActionType.manual_review,
            "The return window has passed. Contact customer support to request a price adjustment.",
        )

    if match and match.same_variant_verified:
        if match.same_seller_verified:
            return (
                ActionType.ask_price_match,
                f"The same product is now cheaper with the same seller. Contact {order.merchant or 'the merchant'} "
                "to request a price match — you're within the return window.",
            )
        else:
            return (
                ActionType.return_and_rebuy,
                "The same product is available cheaper from a different seller. "
                "Consider returning your order and rebuying at the lower price.",
            )

    return (
        ActionType.manual_review,
        "We found a possible price drop but couldn't fully verify it's the same product. "
        "Please review manually.",
    )


async def get_latest_recommendation(order_id: int, db: AsyncSession) -> ActionRecommendation | None:
    result = await db.execute(
        select(ActionRecommendation)
        .where(ActionRecommendation.order_id == order_id)
        .order_by(ActionRecommendation.created_at.desc())
        .limit(1)
    )
    rec = result.scalar_one_or_none()
    if rec:
        return rec
    # Generate on demand if none exists
    return await generate_recommendation(order_id, db)
