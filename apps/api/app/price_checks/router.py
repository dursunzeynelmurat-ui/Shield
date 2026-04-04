from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Order, ProductMatch, PriceCheck, User
from app.monitoring.service import run_price_check
from app.schemas import PriceCheckOut

router = APIRouter(prefix="/price-checks", tags=["price-checks"])


@router.post("/run/{order_id}", response_model=PriceCheckOut, status_code=201)
async def trigger_price_check(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(selectinload(Order.product_matches))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    active = [m for m in order.product_matches if m.is_active]
    if not active:
        raise HTTPException(400, "No active product match")

    match = active[0]
    check = await run_price_check(match, db)
    return check


@router.get("/{order_id}", response_model=list[PriceCheckOut])
async def list_price_checks(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Order not found")

    r = await db.execute(
        select(PriceCheck)
        .join(ProductMatch)
        .where(ProductMatch.order_id == order_id)
        .order_by(PriceCheck.checked_at.desc())
    )
    return r.scalars().all()
