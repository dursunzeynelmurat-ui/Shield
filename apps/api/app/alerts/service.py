"""Alert evaluation logic."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Alert, AlertStatus, AlertType, Order, OrderStatus, PriceCheck, ProductMatch

MIN_SAVINGS_AMOUNT = Decimal("1.00")
MIN_SAVINGS_PERCENT = 0.01  # 1 %

# Fire a return-deadline alert when this many days remain
DEADLINE_WARNING_DAYS = 3


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

    created: list[Alert] = []

    # 1. Price-drop alerts (one per price check)
    for match in order.product_matches:
        if not match.is_active:
            continue
        latest_checks = sorted(
            match.price_checks, key=lambda c: c.checked_at, reverse=True
        )[:1]
        for check in latest_checks:
            alert = await _maybe_price_drop_alert(order, check, db)
            if alert:
                created.append(alert)

    # 2. Return-deadline-approaching alert (once, when ≤ DEADLINE_WARNING_DAYS remain)
    deadline_alert = await _maybe_deadline_alert(order, db)
    if deadline_alert:
        created.append(deadline_alert)

    return created


async def _maybe_price_drop_alert(
    order: Order, check: PriceCheck, db: AsyncSession
) -> Alert | None:
    if not check.success or check.final_price is None or order.purchase_price is None:
        return None

    savings = order.purchase_price - check.final_price
    if savings < MIN_SAVINGS_AMOUNT:
        return None
    if float(savings) / float(order.purchase_price) < MIN_SAVINGS_PERCENT:
        return None

    # Dedup: unique constraint (price_check_id, alert_type) handles concurrent runs;
    # also do a fast pre-check to avoid an unnecessary INSERT attempt.
    existing = await db.execute(
        select(Alert).where(
            Alert.price_check_id == check.id,
            Alert.alert_type == AlertType.price_drop,
        )
    )
    if existing.scalar_one_or_none():
        return None

    alert = Alert(
        order_id=order.id,
        price_check_id=check.id,
        alert_type=AlertType.price_drop,
        amount_saved=savings,
        message=(
            f"Fiyat düştü! {order.purchase_price} {order.currency or 'TRY'} "
            f"yerine şimdi {check.final_price} {check.currency or order.currency or 'TRY'} "
            f"— {savings:.2f} {order.currency or 'TRY'} tasarruf edebilirsiniz."
        ),
        status=AlertStatus.new,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def _maybe_deadline_alert(order: Order, db: AsyncSession) -> Alert | None:
    """
    Fire a ``return_deadline_approaching`` alert when the return window is
    closing (≤ DEADLINE_WARNING_DAYS days left) and we haven't already fired
    one for this order.
    """
    if not order.return_deadline:
        return None

    today = date.today()
    days_left = (order.return_deadline - today).days

    if days_left < 0 or days_left > DEADLINE_WARNING_DAYS:
        return None  # Expired or plenty of time — don't fire

    # Check if we already have a deadline alert for this order
    existing = await db.execute(
        select(Alert).where(
            Alert.order_id == order.id,
            Alert.alert_type == AlertType.return_deadline_approaching,
        )
    )
    if existing.scalar_one_or_none():
        return None  # Already sent once

    if days_left == 0:
        msg = "İade son günü! Bugün iade işlemini başlatın."
    elif days_left == 1:
        msg = "İade süreniz yarın bitiyor. Fırsat varsa bugün harekete geçin."
    else:
        msg = f"İade süreniz {days_left} gün içinde bitiyor. Fiyat düşüşünü değerlendirmek için son şansınız."

    alert = Alert(
        order_id=order.id,
        price_check_id=None,  # Not tied to a specific price check
        alert_type=AlertType.return_deadline_approaching,
        amount_saved=None,
        message=msg,
        status=AlertStatus.new,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert
