"""Discovery router — personalized feed and interest tracking."""
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
from app.discovery.service import get_feed, record_interest_event

router = APIRouter(prefix="/discovery", tags=["discovery"])


class InterestEventIn(BaseModel):
    event_type: str
    product_id: int | None = None
    query: str | None = None
    metadata_json: str | None = None


@router.get("/feed")
async def discovery_feed(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    return await get_feed(db, current_user.id, page, page_size)


@router.post("/interest-events", status_code=201)
async def post_interest_event(
    body: InterestEventIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    return await record_interest_event(
        db,
        user_id=current_user.id,
        event_type=body.event_type,
        product_id=body.product_id,
        query=body.query,
        metadata_json=body.metadata_json,
    )
