from pydantic import BaseModel, ConfigDict, Field

from app.stadium.models import UpgradeType


class StadiumUpgradeBase(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(max_length=255)
    type: UpgradeType
    level: int = Field(default=0, ge=0)
    max_level: int = Field(ge=1)
    price: float = Field(ge=0)
    price_step: float = Field(ge=0)
    multiplier: float = Field(default=1.0, ge=0)
    multiplier_step: float = Field(ge=0)


class StadiumUpgradeCreate(StadiumUpgradeBase):
    pass


class StadiumUpgradeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    type: UpgradeType | None = None
    level: int | None = Field(default=None, ge=0)
    max_level: int | None = Field(default=None, ge=1)
    price: float | None = Field(default=None, ge=0)
    price_step: float | None = Field(default=None, ge=0)
    multiplier: float | None = Field(default=None, ge=0)
    multiplier_step: float | None = Field(default=None, ge=0)


class StadiumUpgradeRead(StadiumUpgradeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class StadiumUpgradeResult(BaseModel):
    """Итог улучшения: paid уже списано в spent финансов клуба."""

    upgrade: StadiumUpgradeRead
    paid: float


class StadiumBonuses(BaseModel):
    income: float
    fans: float
