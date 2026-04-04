"""Affiliate router — click tracking."""
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
from app.affiliate.service import record_click

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


class ClickIn(BaseModel):
    merchant_offer_id: int | None = None
    offer_id: int | None = None
    url: str | None = None


@router.post("/click", status_code=201)
async def affiliate_click(
    body: ClickIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    client_ip = request.client.host if request.client else None
    return await record_click(
        db,
        user_id=current_user.id,
        merchant_offer_id=body.merchant_offer_id,
        offer_id=body.offer_id,
        url=body.url,
        client_ip=client_ip,
    )
