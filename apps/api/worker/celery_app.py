"""Celery application configuration."""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "fiyat_kalkani",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Istanbul",
    enable_utc=True,
    beat_schedule={
        "daily-price-check": {
            "task": "worker.tasks.daily_price_check_job",
            "schedule": 60 * 60 * 24,       # every 24h
        },
        "refresh-prices": {
            "task": "worker.tasks.refresh_prices_job",
            "schedule": 60 * 60,             # every 1h
        },
        "ingest-offers": {
            "task": "worker.tasks.ingest_offers_job",
            "schedule": 60 * 60 * 6,         # every 6h
        },
        "build-feed": {
            "task": "worker.tasks.build_feed_job",
            "schedule": 60 * 60 * 12,        # every 12h
        },
    },
)
