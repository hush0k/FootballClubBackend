from enum import StrEnum

from sqlalchemy import Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlayerStatus(StrEnum):
    SQUAD = "squad"
    MARKET = "market"


class Position(StrEnum):
    GK = "ВР"
    RB = "ПЗ"
    CB = "ЦЗ"
    LB = "ЛЗ"
    DM = "ОП"
    CM = "ЦП"
    AM = "АП"
    RW = "ПВ"
    LW = "ЛВ"
    ST = "ФР"


class LineUp(StrEnum):
    DEPTH = "Глубина состава"
    BENCH = "Запасной состав"
    ROTATION = "Игрок ротации"
    STARTER = "Основной состав"


def _str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        # номер уникален только внутри своей команды (у рыночных игроков номера нет)
        Index(
            "uq_players_squad_number",
            "number",
            unique=True,
            postgresql_where="status = 'squad'",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    nation: Mapped[str] = mapped_column(String(100))
    age: Mapped[int]
    salary: Mapped[float]
    price: Mapped[float]
    power: Mapped[int]
    img_url: Mapped[str] = mapped_column(String(255))
    position: Mapped[Position] = mapped_column(_str_enum(Position, "position"))
    status: Mapped[PlayerStatus] = mapped_column(_str_enum(PlayerStatus, "player_status"), index=True)

    # только для игроков своей команды
    number: Mapped[int | None]
    line_up: Mapped[LineUp | None] = mapped_column(_str_enum(LineUp, "line_up"))

    # только для игроков с рынка — откуда покупаем
    club: Mapped[str | None] = mapped_column(String(100))
    league: Mapped[str | None] = mapped_column(String(100))
