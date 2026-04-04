"""Alert evaluation logic."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Alert, AlertStatus, AlertType, Order, OrderStatus, PriceCheck, ProductMatch

MIN_SAVINGS_AMOUNT = Decimal("1.00")
MIN_SAVINGS_PERCENT = 0.01  # 1%


async def evaluate_alerts_for_order(order_id: int, db: AsyncSession) -> list[Alert]:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.status == OrderStatus.monitoring)
        .options(
            selectinload(Order.product_matches).selectinload(ProductMatch.price_checks)
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        return []

    created = []
    for match in order.product_matches:
        if not match.is_active:
            continue
        for check in sorted(match.price_checks, key=lambda c: c.checked_at, reverse=True)[:1]:
            alert = await _maybe_create_alert(order, check, db)
            if alert:
                created.append(alert)

    return created


async def _maybe_create_alert(order: Order, check: PriceCheck, db: AsyncSession) -> Alert | None:
    if not check.success or check.final_price is None or order.purchase_price is None:
        return None

    savings = order.purchase_price - check.final_price
    if savings < MIN_SAVINGS_AMOUNT:
        return None
    if float(savings) / float(order.purchase_price) < MIN_SAVINGS_PERCENT:
        return None

    # Don't duplicate alerts for same price check
    existing = await db.execute(
        select(Alert).where(Alert.price_check_id == check.id, Alert.alert_type == AlertType.price_drop)
    )
    if existing.scalar_one_or_none():
        return None

    alert = Alert(
        order_id=order.id,
        price_check_id=check.id,
        alert_type=AlertType.price_drop,
        amount_saved=savings,
        message=f"Price dropped from {order.purchase_price} to {check.final_price} {order.currency}",
        status=AlertStatus.new,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert
