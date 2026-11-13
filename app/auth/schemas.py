from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=72)  # bcrypt учитывает максимум 72 байта


class GoogleLogin(BaseModel):
    credential: str = Field(min_length=1)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
