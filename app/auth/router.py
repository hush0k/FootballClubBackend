from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import Token, UserCredentials, UserRead
from app.auth.security import create_access_token
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserCredentials, db: AsyncSession = Depends(get_db)):
    if await service.get_user_by_username(db, data.username):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    try:
        user = await service.create_user(db, data.username, data.password)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
async def login(data: UserCredentials, db: AsyncSession = Depends(get_db)):
    user = await service.authenticate(db, data.username, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    return user
