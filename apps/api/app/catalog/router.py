"""Catalog router — product search and detail."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
from app.catalog.service import get_product_detail, search_products

router = APIRouter(prefix="/catalog", tags=["catalog"])


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
    return await search_products(db, q, category, brand, page, page_size)


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
        "offers": [
            {
                "id": o.id,
                "merchant": o.merchant,
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
        ],
    }
