from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.firebase import verify_firebase_token
from app.database import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    # Verify Firebase ID token
    claims = verify_firebase_token(token)
    if not claims:
        raise credentials_exception

    firebase_uid = claims.get("uid")
    email = claims.get("email")
    if not firebase_uid or not email:
        raise credentials_exception

    # Look up or auto-create user in DB by firebase_uid or email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=email, password_hash="firebase", is_active=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise credentials_exception

    return user
