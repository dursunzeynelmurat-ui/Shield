"""Celery application configuration."""
import sys
import os

# Make app importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from celery import Celery
from app.config import settings

celery_app = Celery(
    "fiyat_kalkani",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["apps.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Istanbul",
    enable_utc=True,
    beat_schedule={
        "daily-price-check": {
            "task": "apps.worker.tasks.daily_price_check_job",
            "schedule": 60 * 60 * 24,  # every 24h
        },
    },
)
