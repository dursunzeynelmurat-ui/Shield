"""Deals router — browse active offers/coupons."""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
from app.deals.service import list_offers

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/offers")
async def get_offers(
    merchant: str | None = Query(default=None, max_length=100),
    discount_type: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Any:
    return await list_offers(db, merchant, discount_type, page, page_size)
