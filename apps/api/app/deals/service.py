"""Deals service — active offers with filtering."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Offer, OfferStatus


async def list_offers(
    db: AsyncSession,
    merchant: str | None,
    discount_type: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    stmt = select(Offer).where(
        and_(
            Offer.status == OfferStatus.active,
            (Offer.expires_at == None) | (Offer.expires_at > now),  # noqa: E711
        )
    )

    if merchant:
        stmt = stmt.where(Offer.merchant == merchant)
    if discount_type:
        stmt = stmt.where(Offer.discount_type == discount_type)

    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Offer.confidence.desc(), Offer.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": o.id,
                "merchant": o.merchant,
                "title": o.title,
                "description": o.description,
                "code": o.code,
                "discount_type": o.discount_type,
                "discount_value": o.discount_value,
                "minimum_spend": o.minimum_spend,
                "conditions": o.conditions,
                "url": o.url,
                "expires_at": o.expires_at,
                "confidence": o.confidence,
            }
            for o in rows
        ],
    }
