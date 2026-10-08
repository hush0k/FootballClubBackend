from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class League(StrEnum):
    """Домашняя лига клуба. В ЛЧ играют и испанские, и иностранные клубы."""

    LALIGA = "laliga"
    FOREIGN = "foreign"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    img_url: Mapped[str] = mapped_column(String(255))
    power: Mapped[int]
    stadium: Mapped[str] = mapped_column(String(100))
    league: Mapped[League] = mapped_column(
        Enum(League, name="league", native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        default=League.LALIGA,
        index=True,
    )
