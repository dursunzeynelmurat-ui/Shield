"""Discovery service — personalized feed and interest event tracking."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Product, RecommendationItem, UserInterestEvent


async def get_feed(
    db: AsyncSession,
    user_id: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    stmt = (
        select(RecommendationItem)
        .where(
            RecommendationItem.user_id == user_id,
            (RecommendationItem.expires_at == None)  # noqa: E711
            | (RecommendationItem.expires_at > now),
        )
        .order_by(RecommendationItem.score.desc(), RecommendationItem.generated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = (await db.execute(stmt)).scalars().all()

    # Load products for the feed items
    product_ids = [i.product_id for i in items]
    products: dict[int, Product] = {}
    if product_ids:
        prod_stmt = select(Product).where(Product.id.in_(product_ids))
        prod_rows = (await db.execute(prod_stmt)).scalars().all()
        products = {p.id: p for p in prod_rows}

    return {
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "reason": i.reason,
                "score": i.score,
                "product": {
                    "name": products[i.product_id].name if i.product_id in products else None,
                    "brand": products[i.product_id].brand if i.product_id in products else None,
                    "image_url": products[i.product_id].image_url if i.product_id in products else None,
                    "category": products[i.product_id].category if i.product_id in products else None,
                }
                if i.product_id in products
                else None,
            }
            for i in items
        ],
    }


async def record_interest_event(
    db: AsyncSession,
    user_id: int,
    event_type: str,
    product_id: int | None,
    query: str | None,
    metadata_json: str | None,
) -> dict[str, Any]:
    event = UserInterestEvent(
        user_id=user_id,
        event_type=event_type,
        product_id=product_id,
        query=query,
        metadata_json=metadata_json,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"id": event.id, "created_at": event.created_at}
