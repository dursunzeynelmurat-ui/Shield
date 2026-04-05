"""Celery tasks for background processing."""
import asyncio
import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    # asyncio.run() creates a fresh event loop each call — safe in Celery workers.
    return asyncio.run(coro)


@celery_app.task(name="worker.tasks.parse_upload_job", bind=True, max_retries=3)
def parse_upload_job(self, upload_id: int, user_id: int):
    from app.database import AsyncSessionLocal
    from app.parsing.service import parse_upload

    async def _inner():
        async with AsyncSessionLocal() as db:
            return await parse_upload(upload_id, user_id, db)

    try:
        return _run(_inner())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="worker.tasks.match_product_job", bind=True, max_retries=3)
def match_product_job(self, order_id: int):
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.matching.service import match_product
    from app.models import Order

    async def _inner():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            if order:
                return await match_product(order, db)

    try:
        return _run(_inner())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="worker.tasks.daily_price_check_job")
def daily_price_check_job():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.database import AsyncSessionLocal
    from app.models import Order, OrderStatus
    from app.monitoring.service import run_price_check
    from app.alerts.service import evaluate_alerts_for_order

    async def _inner():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Order)
                .where(Order.status == OrderStatus.monitoring)
                .options(selectinload(Order.product_matches))
            )
            orders = result.scalars().all()
            for order in orders:
                for match in order.product_matches:
                    if not match.is_active:
                        continue
                    try:
                        await run_price_check(match, db)
                        await evaluate_alerts_for_order(order.id, db)
                    except Exception as exc:
                        logger.warning(
                            "daily_price_check_job: failed for order %s match %s: %s",
                            order.id, match.id, exc,
                        )

    return _run(_inner())


@celery_app.task(name="worker.tasks.alert_evaluator_job")
def alert_evaluator_job(order_id: int):
    from app.database import AsyncSessionLocal
    from app.alerts.service import evaluate_alerts_for_order

    async def _inner():
        async with AsyncSessionLocal() as db:
            return await evaluate_alerts_for_order(order_id, db)

    return _run(_inner())


@celery_app.task(name="worker.tasks.recommendation_job")
def recommendation_job(order_id: int):
    from app.database import AsyncSessionLocal
    from app.actions.service import generate_recommendation

    async def _inner():
        async with AsyncSessionLocal() as db:
            return await generate_recommendation(order_id, db)

    return _run(_inner())


@celery_app.task(name="worker.tasks.ingest_offers_job")
def ingest_offers_job():
    """
    1. Expire offers whose expires_at has passed.
    2. Fetch new deals from each merchant connector and upsert into offers table.
    """
    from datetime import datetime, timezone
    from sqlalchemy import update, select
    from app.database import AsyncSessionLocal
    from app.models import Offer, OfferStatus
    from app.merchants.connector import CONNECTOR_REGISTRY

    async def _inner():
        async with AsyncSessionLocal() as db:
            # Step 1: expire stale offers
            now = datetime.now(timezone.utc)
            await db.execute(
                update(Offer)
                .where(Offer.expires_at.isnot(None), Offer.expires_at < now)
                .values(status=OfferStatus.expired)
            )
            await db.commit()

            # Step 2: fetch new deals from each connector
            for merchant_name, connector in CONNECTOR_REGISTRY.items():
                try:
                    deals = await connector.fetch_deals()
                except Exception as exc:
                    logger.warning("fetch_deals failed for %s: %s", merchant_name, exc)
                    continue

                for deal in deals:
                    title = deal.get("title") or ""
                    if not title:
                        continue
                    # Dedup by merchant + code (if present), or merchant + title
                    code = deal.get("code")
                    existing = None
                    if code:
                        result = await db.execute(
                            select(Offer).where(
                                Offer.merchant == merchant_name,
                                Offer.code == code,
                                Offer.status == OfferStatus.active,
                            )
                        )
                        existing = result.scalar_one_or_none()
                    if existing is None:
                        result = await db.execute(
                            select(Offer).where(
                                Offer.merchant == merchant_name,
                                Offer.title == title,
                                Offer.status == OfferStatus.active,
                            )
                        )
                        existing = result.scalar_one_or_none()

                    if existing:
                        existing.last_seen_at = now
                    else:
                        expires_raw = deal.get("expires_at")
                        expires_dt = None
                        if expires_raw:
                            try:
                                # Accept ISO-8601 strings; strip trailing Z for Python < 3.11
                                expires_dt = datetime.fromisoformat(
                                    str(expires_raw).replace("Z", "+00:00")
                                )
                            except (ValueError, TypeError):
                                pass
                        db.add(Offer(
                            merchant=merchant_name,
                            title=title,
                            code=code,
                            discount_type=deal.get("discount_type"),
                            discount_value=deal.get("discount_value"),
                            minimum_spend=deal.get("minimum_spend"),
                            conditions=deal.get("conditions"),
                            url=deal.get("url"),
                            expires_at=expires_dt,
                            last_seen_at=now,
                            confidence=0.8,
                            status=OfferStatus.active,
                        ))
                await db.commit()

    return _run(_inner())


@celery_app.task(name="worker.tasks.refresh_prices_job")
def refresh_prices_job():
    """
    Re-fetch live prices for all in-stock merchant_offers via connector,
    then append a snapshot to price_history.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models import MerchantOffer, PriceHistory
    from app.merchants.connector import CONNECTOR_REGISTRY

    async def _inner():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MerchantOffer).where(MerchantOffer.in_stock == True)  # noqa: E712
            )
            offers = result.scalars().all()
            now = datetime.now(timezone.utc)

            for offer in offers:
                if not offer.url:
                    continue
                connector = CONNECTOR_REGISTRY.get(offer.merchant)
                if connector is None:
                    # No connector: just snapshot existing price
                    live_price = offer.effective_price
                else:
                    try:
                        data = await connector.fetch_price(offer.url)
                        if data.get("success"):
                            live_price = data.get("final_price") or data.get("listed_price")
                            from decimal import Decimal
                            if live_price is not None:
                                offer.effective_price = Decimal(str(live_price))
                                offer.in_stock = data.get("stock_status") != "out_of_stock"
                        else:
                            live_price = offer.effective_price
                    except Exception as exc:
                        logger.warning("refresh_prices fetch_price failed for offer %s: %s", offer.id, exc)
                        live_price = offer.effective_price

                if live_price is not None:
                    db.add(PriceHistory(
                        product_id=offer.product_id,
                        merchant=offer.merchant,
                        price=live_price,
                        currency=offer.currency or "TRY",
                        recorded_at=now,
                    ))
                offer.last_checked_at = now

            await db.commit()

    return _run(_inner())


@celery_app.task(name="worker.tasks.build_feed_job")
def build_feed_job():
    """
    Build personalized recommendation feed per user, weighted by interest events.
    Clears stale items, then scores catalog products based on category matches
    from the user's recorded interest events.
    """
    from datetime import datetime, timedelta, timezone
    from collections import Counter
    from sqlalchemy import select, delete
    from app.database import AsyncSessionLocal
    from app.models import User, RecommendationItem, UserInterestEvent, Product

    async def _inner():
        async with AsyncSessionLocal() as db:
            users_result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = users_result.scalars().all()

            now = datetime.now(timezone.utc)
            expires = now + timedelta(days=7)

            # Load full catalog once (reasonable for MVP scale)
            catalog_result = await db.execute(select(Product).limit(500))
            catalog_products = catalog_result.scalars().all()

            for user in users:
                # Collect user's interest signals: category_id frequency
                events_result = await db.execute(
                    select(UserInterestEvent)
                    .where(UserInterestEvent.user_id == user.id)
                    .order_by(UserInterestEvent.created_at.desc())
                    .limit(200)
                )
                events = events_result.scalars().all()
                # Build interest signal: products the user has viewed/interacted with
                product_views: set[int] = set()
                category_hits: Counter = Counter()
                for ev in events:
                    if ev.product_id:
                        product_views.add(ev.product_id)
                        # Map product → its category for category-level boosting
                        for p in catalog_products:
                            if p.id == ev.product_id and p.category_id:
                                category_hits[p.category_id] += 1
                                break

                # Clear stale recommendations
                await db.execute(
                    delete(RecommendationItem).where(RecommendationItem.user_id == user.id)
                )

                # Score products: base 0.5 + up to 0.4 for category interest
                scored: list[tuple[float, Product]] = []
                for product in catalog_products:
                    if product.id in product_views:
                        continue  # skip already-seen products
                    score = 0.5
                    if product.category_id and product.category_id in category_hits:
                        score += min(category_hits[product.category_id] * 0.1, 0.4)
                    scored.append((score, product))

                scored.sort(key=lambda x: x[0], reverse=True)

                for score, product in scored[:20]:
                    reason = "interest_match" if score > 0.5 else "catalog_match"
                    db.add(RecommendationItem(
                        user_id=user.id,
                        product_id=product.id,
                        reason=reason,
                        score=score,
                        generated_at=now,
                        expires_at=expires,
                    ))

                await db.commit()

    return _run(_inner())
