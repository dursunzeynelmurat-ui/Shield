"""
Live search fallback
====================
When the catalog DB returns zero results for a query, this module calls
the merchant connectors in parallel, ingests whatever they return into the
products/merchant_offers tables, then re-queries the DB.

This bridges the gap between an empty catalog and real product data:
  GET /catalog/search?q=... → DB miss → connector search → ingest → DB hit
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import ingest_batch
from app.models import Product

logger = logging.getLogger(__name__)


def _to_ingest(raw: dict, brand: str | None) -> dict | None:
    """Map a connector search result to the ingest_batch input format."""
    title = raw.get("title") or raw.get("name", "")
    if not title:
        return None
    return {
        # ingest_batch _extract_field keys:
        "name": title,
        "brand": raw.get("brand") or brand,
        "price": raw.get("price"),
        "discountedPrice": raw.get("price"),  # treat search price as effective
        "currency": raw.get("currency", "TRY"),
        "url": raw.get("url") or raw.get("product_url"),
        "sellerName": raw.get("seller"),
        "imageUrl": raw.get("image_url"),
    }


async def live_search_and_seed(
    db: AsyncSession,
    q: str,
    brand: str | None,
    page: int,
    page_size: int,
) -> dict:
    """
    Call all registered connectors for *q*, ingest the results, re-query DB.

    Returns the same shape as ``search_products()``:
    ``{"total": N, "page": P, "page_size": S, "items": [Product, ...]}``.
    """
    # Import here to avoid circular import at module load time
    from app.merchants.connector import _CONNECTORS  # noqa: PLC0415

    if not _CONNECTORS:
        logger.warning("live_search_and_seed: no connectors registered")
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    # ── 1. Call all connectors in parallel ───────────────────────────────
    tasks = [conn.search(q, brand, None) for conn in _CONNECTORS.values()]
    merchant_names = list(_CONNECTORS.keys())
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # ── 2. Ingest per-merchant ────────────────────────────────────────────
    ingested_any = False
    for merchant, results in zip(merchant_names, all_results):
        if isinstance(results, Exception):
            logger.warning("Connector %s raised during live search: %s", merchant, results)
            continue
        if not results:
            logger.debug("Connector %s returned 0 results for %r", merchant, q)
            continue

        batch = [d for r in results if (d := _to_ingest(r, brand)) is not None]
        if not batch:
            continue

        try:
            summary = await ingest_batch(db, batch, merchant)
            logger.info(
                "live_search_and_seed: %s ingested %d created / %d updated for %r",
                merchant, summary["created"], summary["updated"], q,
            )
            ingested_any = True
        except Exception as exc:
            logger.warning("Ingest failed for connector %s: %s", merchant, exc)

    if not ingested_any:
        logger.info("live_search_and_seed: all connectors returned empty for %r", q)
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    # ── 3. Re-query DB (bypass the @cached layer — direct query) ─────────
    q_like = f"%{q.lower()}%"
    stmt = select(Product).where(
        or_(
            func.lower(Product.normalized_name).like(q_like),
            func.lower(Product.name).like(q_like),
            func.lower(Product.brand).like(q_like),
        )
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Product.name).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    logger.info("live_search_and_seed: DB has %d products matching %r after seed", total, q)
    return {"total": total, "page": page, "page_size": page_size, "items": rows}
