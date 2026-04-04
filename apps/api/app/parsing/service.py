"""Parse an upload into structured order data."""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderStatus, Upload, UploadStatus
from app.parsing.adapter import get_parsing_adapter
from app.schemas import ParsedOrderData
from app.uploads.storage import get_storage


async def parse_upload(upload_id: int, user_id: int, db: AsyncSession) -> Order:
    result = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.user_id == user_id)
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise ValueError(f"Upload {upload_id} not found")

    upload.status = UploadStatus.processing
    await db.commit()

    storage = get_storage()
    local_path = storage.get_local_path(upload.storage_url)

    adapter = get_parsing_adapter()
    parsed: ParsedOrderData = await adapter.parse_image(local_path)

    upload.status = UploadStatus.parsed
    await db.commit()

    order = Order(
        user_id=user_id,
        upload_id=upload_id,
        merchant=parsed.merchant,
        merchant_order_no=parsed.merchant_order_no,
        product_title_raw=parsed.product_title_raw,
        normalized_title=_normalize_title(parsed.product_title_raw),
        brand=parsed.brand,
        model=parsed.model,
        variant=parsed.variant,
        sku=parsed.sku,
        seller_name=parsed.seller_name,
        purchase_price=parsed.purchase_price,
        currency=parsed.currency or "TRY",
        purchased_at=parsed.purchased_at,
        delivery_date=parsed.delivery_date,
        return_deadline=parsed.return_deadline,
        parse_confidence=parsed.confidence,
        parse_raw=json.dumps(parsed.raw_extraction) if parsed.raw_extraction else None,
        status=OrderStatus.pending_verification,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


def _normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    import re
    # Lowercase, collapse whitespace, strip punctuation noise
    t = title.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t
