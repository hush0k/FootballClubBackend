from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CoachRole(StrEnum):
    HEAD = "Главный тренер"
    SECOND = "Второй тренер"
    ASSISTANT = "Ассистент тренера"
    GOALKEEPING = "Тренер вратарей"
    FITNESS = "Тренер по физподготовке"
    ANALYST = "Главный аналитик"


class Coach(Base):
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int]
    role: Mapped[CoachRole] = mapped_column(
        Enum(
            CoachRole,
            name="coach_role",
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    salary: Mapped[float]
    power: Mapped[int]
