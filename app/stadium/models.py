from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UpgradeType(StrEnum):
    INCOME = "income"  # доход за победу
    FANS = "fans"  # прирост болельщиков


class StadiumUpgrade(Base):
    __tablename__ = "stadium_upgrades"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    type: Mapped[UpgradeType] = mapped_column(
        Enum(
            UpgradeType,
            name="upgrade_type",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    level: Mapped[int] = mapped_column(default=0)
    max_level: Mapped[int]
    # price — цена следующего уровня, растёт на price_step после каждого улучшения
    price: Mapped[float]
    price_step: Mapped[float]
    multiplier: Mapped[float] = mapped_column(default=1.0)
    multiplier_step: Mapped[float]
