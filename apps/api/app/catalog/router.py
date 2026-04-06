"""Catalog router — product search, detail, and ingest."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Category, User
from app.catalog.service import get_product_detail, search_products
from app.catalog.ingest import ingest_batch
from app.catalog.classifier import classify, parse_merchant_path

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories")
async def list_categories(
    parent_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Any:
    """List categories.  Pass ``parent_id`` to list children of a node."""
    stmt = select(Category)
    if parent_id is not None:
        stmt = stmt.where(Category.parent_id == parent_id)
    else:
        stmt = stmt.where(Category.parent_id == None)  # noqa: E711  root level
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "path": c.path,
            "depth": c.depth,
            "parent_id": c.parent_id,
        }
        for c in rows
    ]


class ClassifyRequest(BaseModel):
    raw_category: str
    merchant: str = "trendyol"


@router.post("/classify")
async def classify_category(
    body: ClassifyRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Any:
    """
    Test endpoint: resolve a raw merchant category string to a canonical Category.
    Shows the parsed path and the matched/created category.
    """
    parsed = parse_merchant_path(body.raw_category, body.merchant)
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse category string")

    cat = await classify(db, body.raw_category, body.merchant)
    await db.commit()

    return {
        "parsed_segments": parsed.segments,
        "parsed_slugs": parsed.slugs,
        "parsed_paths": parsed.paths,
        "category": {
            "id": cat.id,
            "name": cat.name,
            "path": cat.path,
            "depth": cat.depth,
        } if cat else None,
    }


class IngestRequest(BaseModel):
    merchant: str
    products: list[dict]


@router.post("/ingest")
async def ingest_products(
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Any:
    """
    Bulk ingest raw product dicts from a merchant API response.
    Auto-classifies categories and upserts products + merchant_offers.
    """
    if not body.products:
        raise HTTPException(status_code=422, detail="products list is empty")
    if len(body.products) > 500:
        raise HTTPException(status_code=422, detail="Max 500 products per request")

    summary = await ingest_batch(db, body.products, body.merchant)
    return summary


@router.get("/search")
async def catalog_search(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=100),
    brand: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Any:
    result = await search_products(db, q, category, brand, page, page_size)

    # Live fallback: when the catalog has no match for a keyword query,
    # call connectors, ingest results, and re-query.  Skipped when filtering
    # by category/brand alone (no keyword) or when results are already found.
    if result["total"] == 0 and q and not category:
        from app.catalog.live import live_search_and_seed  # noqa: PLC0415
        result = await live_search_and_seed(db, q, brand, page, page_size)

    return result


@router.get("/products/{product_id}")
async def catalog_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Any:
    product = await get_product_detail(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Build response with sorted offers
    offers_sorted = sorted(
        product.merchant_offers,
        key=lambda o: (o.effective_price or o.listed_price or 0),
    )

    offers_data = [
        {
            "id": o.id,
            "merchant": o.merchant.capitalize(),
            "seller_name": o.seller_name,
            "url": o.url,
            "listed_price": o.listed_price,
            "shipping_price": o.shipping_price,
            "effective_price": o.effective_price,
            "currency": o.currency,
            "in_stock": o.in_stock,
            "last_checked_at": o.last_checked_at,
        }
        for o in offers_sorted
    ]

    compare = None
    if len(offers_sorted) >= 2:
        best = offers_sorted[0]
        next_ = offers_sorted[1]
        best_price = best.effective_price or best.listed_price or 0
        next_price = next_.effective_price or next_.listed_price or 0
        if best_price > 0 and next_price > best_price:
            diff = next_price - best_price
            pct = (diff / next_price * 100)
            compare = {
                "best_price": best_price,
                "best_merchant": best.merchant.capitalize(),
                "best_url": best.url,
                "next_price": next_price,
                "next_merchant": next_.merchant.capitalize(),
                "next_url": next_.url,
                "you_save": diff,
                "you_save_pct": round(float(pct), 1),
                "currency": best.currency,
            }

    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "model": product.model,
        "category": product.category,
        "description": product.description,
        "image_url": product.image_url,
        "ean": product.ean,
        "created_at": product.created_at,
        "offers": offers_data,
        "compare": compare,
    }
