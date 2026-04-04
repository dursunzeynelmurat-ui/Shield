"""Affiliate service — click tracking."""
import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AffiliateClick


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()


async def record_click(
    db: AsyncSession,
    user_id: int | None,
    merchant_offer_id: int | None,
    offer_id: int | None,
    url: str | None,
    client_ip: str | None,
) -> dict[str, Any]:
    click = AffiliateClick(
        user_id=user_id,
        merchant_offer_id=merchant_offer_id,
        offer_id=offer_id,
        url=url,
        ip_hash=_hash_ip(client_ip) if client_ip else None,
    )
    db.add(click)
    await db.commit()
    await db.refresh(click)
    return {"id": click.id, "clicked_at": click.clicked_at}
