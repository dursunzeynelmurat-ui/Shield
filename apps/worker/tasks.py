"""Celery tasks for background processing."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from celery import shared_task

from apps.worker.celery_app import celery_app


def _run(coro):
    # asyncio.run() creates a fresh event loop each call — safe in Celery workers.
    # get_event_loop() is deprecated in Python 3.10+ when no loop is running.
    return asyncio.run(coro)


@celery_app.task(name="apps.worker.tasks.parse_upload_job", bind=True, max_retries=3)
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


@celery_app.task(name="apps.worker.tasks.match_product_job", bind=True, max_retries=3)
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


@celery_app.task(name="apps.worker.tasks.daily_price_check_job")
def daily_price_check_job():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.database import AsyncSessionLocal
    from app.models import Order, OrderStatus, ProductMatch
    from app.monitoring.service import run_price_check

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
                    if match.is_active:
                        await run_price_check(match, db)
                        await alert_evaluator_job_inner(order.id, db)

    return _run(_inner())


@celery_app.task(name="apps.worker.tasks.alert_evaluator_job")
def alert_evaluator_job(order_id: int):
    from app.database import AsyncSessionLocal
    from app.alerts.service import evaluate_alerts_for_order

    async def _inner():
        async with AsyncSessionLocal() as db:
            return await evaluate_alerts_for_order(order_id, db)

    return _run(_inner())


async def alert_evaluator_job_inner(order_id: int, db):
    from app.alerts.service import evaluate_alerts_for_order
    return await evaluate_alerts_for_order(order_id, db)


@celery_app.task(name="apps.worker.tasks.recommendation_job")
def recommendation_job(order_id: int):
    from app.database import AsyncSessionLocal
    from app.actions.service import generate_recommendation

    async def _inner():
        async with AsyncSessionLocal() as db:
            return await generate_recommendation(order_id, db)

    return _run(_inner())


@celery_app.task(name="apps.worker.tasks.ingest_offers_job")
def ingest_offers_job():
    """Fetch coupon/offer data from merchant connectors and upsert into offers table."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.database import AsyncSessionLocal
    from app.models import Offer, OfferStatus

    async def _inner():
        async with AsyncSessionLocal() as db:
            # Expire offers whose expires_at has passed
            from sqlalchemy import update
            now = datetime.now(timezone.utc)
            await db.execute(
                update(Offer)
                .where(Offer.expires_at != None, Offer.expires_at < now)  # noqa: E711
                .values(status=OfferStatus.expired)
            )
            await db.commit()

    return _run(_inner())


@celery_app.task(name="apps.worker.tasks.refresh_prices_job")
def refresh_prices_job():
    """Re-check prices for all active merchant_offers and append to price_history."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models import MerchantOffer, PriceHistory

    async def _inner():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MerchantOffer).where(MerchantOffer.in_stock == True)  # noqa: E712
            )
            offers = result.scalars().all()
            now = datetime.now(timezone.utc)
            for offer in offers:
                if offer.effective_price is not None:
                    history_entry = PriceHistory(
                        product_id=offer.product_id,
                        merchant=offer.merchant,
                        price=offer.effective_price,
                        currency=offer.currency or "TRY",
                        recorded_at=now,
                    )
                    db.add(history_entry)
                    offer.last_checked_at = now
            await db.commit()

    return _run(_inner())


@celery_app.task(name="apps.worker.tasks.build_feed_job")
def build_feed_job():
    """Build personalized recommendation feed for all active users."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, delete
    from app.database import AsyncSessionLocal
    from app.models import User, RecommendationItem

    async def _inner():
        async with AsyncSessionLocal() as db:
            # Get all active users
            users_result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = users_result.scalars().all()

            now = datetime.now(timezone.utc)
            expires = now + timedelta(days=7)

            for user in users:

                # Clear stale recommendations for this user
                await db.execute(
                    delete(RecommendationItem).where(
                        RecommendationItem.user_id == user.id
                    )
                )

                from app.models import Product as CatalogProduct  # noqa: F811
                catalog_result = await db.execute(
                    select(CatalogProduct).limit(20)
                )
                catalog_products = catalog_result.scalars().all()

                seen_products: set[int] = set()
                for cp in catalog_products:
                    if cp.id in seen_products:
                        continue
                    seen_products.add(cp.id)
                    item = RecommendationItem(
                        user_id=user.id,
                        product_id=cp.id,
                        reason="catalog_match",
                        score=0.5,
                        generated_at=now,
                        expires_at=expires,
                    )
                    db.add(item)

                await db.commit()

    return _run(_inner())
