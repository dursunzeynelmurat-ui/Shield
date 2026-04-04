"""Catalog service — product search and detail."""
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MerchantOffer, Product


async def search_products(
    db: AsyncSession,
    q: str | None,
    category: str | None,
    brand: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    stmt = select(Product)

    if q:
        q_like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.normalized_name).like(q_like),
                func.lower(Product.name).like(q_like),
                func.lower(Product.brand).like(q_like),
            )
        )
    if category:
        stmt = stmt.where(func.lower(Product.category) == category.lower())
    if brand:
        stmt = stmt.where(func.lower(Product.brand) == brand.lower())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Product.name).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": rows,
    }


async def get_product_detail(db: AsyncSession, product_id: int) -> Product | None:
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.merchant_offers))
    )
    return (await db.execute(stmt)).scalar_one_or_none()
