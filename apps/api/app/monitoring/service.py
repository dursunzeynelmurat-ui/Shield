"""Price checking pipeline."""
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.merchants.connector import get_connector
from app.models import CheckMethod, PriceCheck, ProductMatch


async def run_price_check(product_match: ProductMatch, db: AsyncSession) -> PriceCheck:
    connector = get_connector(product_match.merchant)

    result = await connector.fetch_price(product_match.matched_url or "")

    price_check = PriceCheck(
        product_match_id=product_match.id,
        checked_at=datetime.now(timezone.utc),
        listed_price=result.get("listed_price"),
        shipping_price=result.get("shipping_price"),
        final_price=result.get("final_price"),
        currency=result.get("currency", "TRY"),
        seller_name=result.get("seller"),
        stock_status=result.get("stock_status"),
        coupon_detected=result.get("coupon_detected", False),
        coupon_text=result.get("coupon_text"),
        check_method=CheckMethod.selector,
        evidence_image_url=result.get("evidence_image_url"),
        raw_payload=json.dumps(result),
        success=result.get("success", False),
        error_message=result.get("error_message"),
    )
    db.add(price_check)
    await db.commit()
    await db.refresh(price_check)
    return price_check
