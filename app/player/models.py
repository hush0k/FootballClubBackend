from enum import StrEnum

from sqlalchemy import Enum, Index, String, text
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
    ACADEMY = "Воспитанник"  # играет в академии, только ему доступны тренировки


class Training(StrEnum):
    NONE = "Без тренировок"
    MODERATE = "Умеренная тренировка"
    NORMAL = "Обычная тренировка"
    INTENSIVE = "Интенсивная тренировка"


# вес тренировки в лимите академии
TRAINING_WEIGHTS = {
    Training.NONE: 0,
    Training.MODERATE: 1,
    Training.NORMAL: 2,
    Training.INTENSIVE: 3,
}


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
    potential: Mapped[int]  # предел силы: от текущей силы до 99, тренировки выше не поднимают
    img_url: Mapped[str] = mapped_column(String(255))
    position: Mapped[Position] = mapped_column(_str_enum(Position, "position"))
    status: Mapped[PlayerStatus] = mapped_column(_str_enum(PlayerStatus, "player_status"), index=True)

    # только для игроков своей команды
    number: Mapped[int | None]
    line_up: Mapped[LineUp | None] = mapped_column(_str_enum(LineUp, "line_up"))

    # тренировки воспитанников: прогресс копится каждую неделю (матч), раз в 3 недели переходит в силу
    training: Mapped[Training] = mapped_column(
        _str_enum(Training, "training"), default=Training.NONE, server_default=Training.NONE.value
    )
    training_progress: Mapped[int] = mapped_column(default=0, server_default=text("0"))  # % за текущий цикл
    training_weeks: Mapped[int] = mapped_column(default=0, server_default=text("0"))  # недель в цикле, 0–2
    power_growth: Mapped[float] = mapped_column(default=0, server_default=text("0"))  # дробный остаток прироста силы
    # переведён из академии в основную команду — вернуть обратно нельзя
    left_academy: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    # только для игроков с рынка — откуда покупаем
    club: Mapped[str | None] = mapped_column(String(100))
    league: Mapped[str | None] = mapped_column(String(100))
