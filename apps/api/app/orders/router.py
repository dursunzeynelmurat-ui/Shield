from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Alert, Order, OrderStatus, ProductMatch, User
from app.parsing.service import parse_upload
from app.schemas import (
    ActionRecommendationOut, AlertOut, DashboardCard, OrderOut, OrderVerifyRequest,
    ProductMatchOut,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/from-upload/{upload_id}", response_model=OrderOut, status_code=201)
async def create_order_from_upload(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await parse_upload(upload_id, current_user.id, db)
    return order


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@router.patch("/{order_id}/verify", response_model=OrderOut)
async def verify_order(
    order_id: int,
    body: OrderVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(order, field, value)

    order.status = OrderStatus.verified
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/{order_id}/match", response_model=ProductMatchOut, status_code=201)
async def match_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.matching.service import match_product
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status not in (OrderStatus.verified, OrderStatus.matching):
        raise HTTPException(400, f"Order must be verified before matching (current: {order.status})")

    product_match = await match_product(order, db)
    return product_match


@router.post("/{order_id}/start-monitoring", response_model=OrderOut)
async def start_monitoring(
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

    active_matches = [m for m in order.product_matches if m.is_active]
    if not active_matches:
        raise HTTPException(400, "No active product match — run matching first")

    order.status = OrderStatus.monitoring
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/{order_id}/stop-monitoring", response_model=OrderOut)
async def stop_monitoring(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    order.status = OrderStatus.completed
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/{order_id}/recommendation", response_model=ActionRecommendationOut | None)
async def get_recommendation(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.actions.service import get_latest_recommendation
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    return await get_latest_recommendation(order_id, db)


@router.get("/{order_id}/matches", response_model=list[ProductMatchOut])
async def list_matches(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Order not found")

    r = await db.execute(select(ProductMatch).where(ProductMatch.order_id == order_id))
    return r.scalars().all()
