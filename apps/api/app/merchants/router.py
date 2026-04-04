from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Merchant, User

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("")
async def list_merchants(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Merchant))
    return result.scalars().all()
