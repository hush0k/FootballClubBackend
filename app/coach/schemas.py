from pydantic import BaseModel, ConfigDict, Field

from app.coach.models import CoachRole


class CoachBase(BaseModel):
    name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    age: int = Field(ge=18, le=90)
    role: CoachRole
    salary: float = Field(ge=0)
    power: int = Field(ge=0, le=100)


class CoachCreate(CoachBase):
    pass


class CoachUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=18, le=90)
    role: CoachRole | None = None
    salary: float | None = Field(default=None, ge=0)
    power: int | None = Field(default=None, ge=0, le=100)


class CoachRead(CoachBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
