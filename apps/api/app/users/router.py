from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.auth.security import hash_password, verify_password
from app.database import get_db
from app.models import Alert, AlertStatus, Order, OrderStatus, ProductMatch, PriceCheck, User
from app.schemas import (
    ChangePasswordRequest, DashboardCard, UserOut, UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update profile fields (email)."""
    if body.email and body.email != current_user.email:
        current_user.email = body.email
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(400, "Email already in use")
        await db.refresh(current_user)
    return current_user


@router.post("/me/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change password. Requires current password for verification."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(400, "New password must differ from current password")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()


@router.delete("/me", status_code=204)
async def delete_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate account (soft delete)."""
    current_user.is_active = False
    await db.commit()


@router.get("/me/dashboard", response_model=list[DashboardCard])
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(
            selectinload(Order.product_matches).selectinload(ProductMatch.price_checks),
            selectinload(Order.alerts),
        )
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()

    cards = []
    for order in orders:
        current_price = None
        active_matches = [m for m in order.product_matches if m.is_active]
        if active_matches:
            checks = sorted(
                [c for m in active_matches for c in m.price_checks if c.success],
                key=lambda c: c.checked_at,
                reverse=True,
            )
            if checks:
                current_price = checks[0].final_price

        savings = None
        if order.purchase_price and current_price:
            diff = order.purchase_price - current_price
            if diff > 0:
                savings = diff

        remaining_days = None
        if order.return_deadline:
            remaining_days = max(0, (order.return_deadline - date.today()).days)

        has_alert = any(a.status == AlertStatus.new for a in order.alerts)

        cards.append(DashboardCard(
            order_id=order.id,
            product_name=order.product_title_raw,
            purchase_price=order.purchase_price,
            current_price=current_price,
            currency=order.currency,
            savings=savings,
            remaining_return_days=remaining_days,
            status=order.status,
            has_alert=has_alert,
        ))

    return cards
