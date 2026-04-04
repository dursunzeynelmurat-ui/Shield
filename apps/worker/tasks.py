"""Celery tasks for background processing."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from celery import shared_task

from apps.worker.celery_app import celery_app


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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
