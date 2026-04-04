"""Watchlist router — add/remove/list catalog products for price tracking."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import MerchantOffer, Product, User, Watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAddIn(BaseModel):
    product_id: int
    target_price: float | None = None


@router.get("")
async def list_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return all watchlist entries for the current user, with product info."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == current_user.id)
        .options(selectinload(Watchlist.product).selectinload(Product.merchant_offers))
        .order_by(Watchlist.created_at.desc())
    )
    items = result.scalars().all()

    return [
        {
            "id": w.id,
            "product_id": w.product_id,
            "target_price": w.target_price,
            "created_at": w.created_at,
            "product": {
                "name": w.product.name if w.product else None,
                "brand": w.product.brand if w.product else None,
                "image_url": w.product.image_url if w.product else None,
                "category": w.product.category if w.product else None,
                "lowest_price": _lowest_price(w.product.merchant_offers if w.product else []),
            },
        }
        for w in items
    ]


@router.post("", status_code=201)
async def add_to_watchlist(
    body: WatchlistAddIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Add a catalog product to the user's watchlist."""
    # Verify product exists
    product = (await db.execute(
        select(Product).where(Product.id == body.product_id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    entry = Watchlist(
        user_id=current_user.id,
        product_id=body.product_id,
        target_price=body.target_price,
    )
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Product already in watchlist")
    await db.refresh(entry)
    return {"id": entry.id, "product_id": entry.product_id, "target_price": entry.target_price}


@router.delete("/{product_id}", status_code=204)
async def remove_from_watchlist(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a product from the watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.product_id == product_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    await db.delete(entry)
    await db.commit()


def _lowest_price(offers: list[MerchantOffer]) -> float | None:
    """Return the lowest effective_price across in-stock offers."""
    prices = [
        float(o.effective_price or o.listed_price)
        for o in offers
        if o.in_stock and (o.effective_price or o.listed_price) is not None
    ]
    return min(prices) if prices else None
