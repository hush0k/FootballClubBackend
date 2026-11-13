import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password, verify_password


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(select(User).where(User.username == username))


async def create_user(db: AsyncSession, username: str, password: str) -> User:
    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if user is None or user.hashed_password is None or not verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_by_google_id(db: AsyncSession, google_id: str) -> User | None:
    return await db.scalar(select(User).where(User.google_id == google_id))


async def _unique_username(db: AsyncSession, email: str | None) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "", (email or "").split("@")[0])[:40] or "user"
    if len(base) < 3:
        base = f"{base}user"
    candidate = base
    suffix = 1
    while await get_user_by_username(db, candidate):
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


async def get_or_create_google_user(db: AsyncSession, google_id: str, email: str | None) -> User:
    user = await get_user_by_google_id(db, google_id)
    if user is not None:
        return user
    user = User(username=await _unique_username(db, email), google_id=google_id)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
