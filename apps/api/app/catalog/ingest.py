"""
Catalog ingest service
======================
Accepts a batch of raw product dicts from merchant APIs (Trendyol,
Hepsiburada, etc.), classifies their categories automatically, and
upserts them into the ``products`` + ``merchant_offers`` tables.

Designed to be called from:
  - The ``ingest_offers_job`` Celery task
  - The ``POST /catalog/ingest`` internal endpoint
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MerchantOffer, PriceHistory, Product
from app.catalog.classifier import (
    assign_category_to_product,
    extract_category_string,
)

logger = logging.getLogger(__name__)


def _to_decimal(val) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except InvalidOperation:
        return None


def _extract_field(product: dict, *keys: str, default=None):
    """Try multiple key names, return first found value."""
    for k in keys:
        if (v := product.get(k)) is not None:
            return v
    return default


def _normalise_name(name: str) -> str:
    """Lowercase + collapse whitespace for dedup matching."""
    return " ".join(name.lower().split())


async def upsert_product(
    db: AsyncSession,
    raw: dict,
    merchant: str,
) -> tuple[Product, bool]:
    """
    Upsert a single product from a raw merchant dict.

    Returns ``(product, created)`` where ``created`` is True for new rows.

    The function does **not** commit — caller controls the transaction.
    """
    # --- Extract core fields -------------------------------------------
    name = str(
        _extract_field(raw, "name", "title", "productName", "urunAdi")
        or "Unknown"
    )
    brand = _extract_field(raw, "brand", "brandName", "marka")
    model = _extract_field(raw, "model", "modelName")
    ean = _extract_field(raw, "barcode", "ean", "gtin", "barcodeList")
    if isinstance(ean, list):
        ean = ean[0] if ean else None
    image_url = _extract_field(raw, "imageUrl", "image_url", "images")
    if isinstance(image_url, list):
        image_url = image_url[0] if image_url else None
    description = _extract_field(raw, "description", "shortDescription")

    # --- Price fields ---------------------------------------------------
    listed_price = _to_decimal(
        _extract_field(raw, "price", "listedPrice", "originalPrice", "salePrice")
    )
    shipping_price = _to_decimal(
        _extract_field(raw, "shippingPrice", "cargoPrice", "shipping_cost")
    )
    effective_price = _to_decimal(
        _extract_field(raw, "discountedPrice", "salePrice", "finalPrice")
    ) or listed_price
    currency = str(_extract_field(raw, "currency", "currencyCode") or "TRY")
    in_stock_raw = _extract_field(raw, "inStock", "in_stock", "stockStatus", "quantity")
    if isinstance(in_stock_raw, str):
        in_stock = in_stock_raw.lower() not in ("false", "0", "out_of_stock", "stok_yok")
    elif isinstance(in_stock_raw, (int, float)):
        in_stock = in_stock_raw > 0
    else:
        in_stock = bool(in_stock_raw) if in_stock_raw is not None else True

    offer_url = _extract_field(raw, "url", "productUrl", "link")
    seller_name = _extract_field(raw, "sellerName", "seller", "storeName")

    # --- Find or create Product ----------------------------------------
    created = False
    product: Product | None = None

    # EAN lookup (most reliable dedup key)
    if ean:
        result = await db.execute(select(Product).where(Product.ean == str(ean)))
        product = result.scalar_one_or_none()

    # Name + brand fuzzy dedup fallback
    if product is None and name:
        norm = _normalise_name(name)
        result = await db.execute(
            select(Product).where(Product.normalized_name == norm)
        )
        product = result.scalar_one_or_none()

    if product is None:
        product = Product(
            name=name,
            normalized_name=_normalise_name(name),
            brand=str(brand) if brand else None,
            model=str(model) if model else None,
            ean=str(ean) if ean else None,
            image_url=str(image_url) if image_url else None,
            description=str(description) if description else None,
        )
        db.add(product)
        await db.flush()  # get product.id
        created = True
    else:
        # Update mutable fields if we have better data
        if brand and not product.brand:
            product.brand = str(brand)
        if image_url and not product.image_url:
            product.image_url = str(image_url)
        if description and not product.description:
            product.description = str(description)

    # --- Classify category ----------------------------------------------
    raw_cat = extract_category_string(raw, merchant)
    await assign_category_to_product(db, product, raw_cat, merchant)

    # --- Upsert MerchantOffer ------------------------------------------
    result = await db.execute(
        select(MerchantOffer).where(
            MerchantOffer.product_id == product.id,
            MerchantOffer.merchant == merchant,
            MerchantOffer.seller_name == (str(seller_name) if seller_name else None),
        )
    )
    offer = result.scalar_one_or_none()

    if offer is None:
        offer = MerchantOffer(
            product_id=product.id,
            merchant=merchant,
            seller_name=str(seller_name) if seller_name else None,
            url=str(offer_url) if offer_url else None,
            listed_price=listed_price,
            shipping_price=shipping_price,
            effective_price=effective_price,
            currency=currency,
            in_stock=in_stock,
        )
        db.add(offer)
        # Record initial price in history
        if effective_price is not None:
            db.add(PriceHistory(
                product_id=product.id,
                merchant=merchant,
                price=effective_price,
                currency=currency,
            ))
    else:
        price_changed = (
            effective_price is not None
            and offer.effective_price != effective_price
        )
        offer.listed_price = listed_price
        offer.shipping_price = shipping_price
        offer.effective_price = effective_price
        offer.in_stock = in_stock
        offer.currency = currency
        if offer_url:
            offer.url = str(offer_url)
        # Record price change in history
        if price_changed:
            db.add(PriceHistory(
                product_id=product.id,
                merchant=merchant,
                price=effective_price,
                currency=currency,
            ))

    return product, created


async def ingest_batch(
    db: AsyncSession,
    items: list[dict],
    merchant: str,
) -> dict[str, int]:
    """
    Ingest a list of raw merchant product dicts.

    Returns summary: ``{"created": N, "updated": M, "errors": E}``.
    Commits once after the entire batch.
    """
    created_count = updated_count = error_count = 0

    for raw in items:
        # Use a savepoint so a single-row failure doesn't abort the whole batch.
        async with db.begin_nested():
            try:
                _, created = await upsert_product(db, raw, merchant)
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as exc:
                logger.warning("Failed to ingest product from %s: %s | raw=%r", merchant, exc, raw)
                error_count += 1

    await db.commit()
    return {"created": created_count, "updated": updated_count, "errors": error_count}
