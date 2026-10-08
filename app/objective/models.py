from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ObjectiveType(StrEnum):
    LALIGA_PLACE = "laliga_place"  # место в Ла Лиге, уровни 1–4
    CHAMPIONS_LEAGUE = "champions_league"  # стадия ЛЧ, уровни 1–3
    REJUVENATE = "rejuvenate"  # омолодить состав, без уровня
    STAR_PLAYER = "star_player"  # купить звёздного игрока, без уровня
    EL_CLASICO = "el_clasico"  # очки в матчах с Барселоной, уровни 1–4


class ObjectiveStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


# у этих целей прогресс должен быть не больше target (место, возраст), у остальных — не меньше
LOWER_IS_BETTER = {ObjectiveType.LALIGA_PLACE, ObjectiveType.REJUVENATE}


def _str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(enum_cls, name=name, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class ClubObjective(Base):
    """Цель клуба на сезон. Награда (млн) начисляется в конце сезона, если цель выполнена, иначе — штраф."""

    __tablename__ = "club_objectives"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(index=True)
    type: Mapped[ObjectiveType] = mapped_column(_str_enum(ObjectiveType, "objective_type"))
    level: Mapped[int | None]
    target: Mapped[int]
    condition: Mapped[str] = mapped_column(String(255))
    reward: Mapped[float]
    penalty: Mapped[float]
    progress: Mapped[float] = mapped_column(default=0)
    status: Mapped[ObjectiveStatus] = mapped_column(
        _str_enum(ObjectiveStatus, "objective_status"), default=ObjectiveStatus.ACTIVE,
    )

    @property
    def achieved(self) -> bool:
        if self.type in LOWER_IS_BETTER:
            return self.progress <= self.target
        return self.progress >= self.target


class ObjectiveState(Base):
    """Номер сезона и уровни лестниц целей — одна строка на всю игру."""

    __tablename__ = "club_objective_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(default=1)
    # сезон завершён (finish_season), награды и штрафы уже начислены
    finished: Mapped[bool] = mapped_column(default=False)
    laliga_level: Mapped[int] = mapped_column(default=1)
    champions_league_level: Mapped[int] = mapped_column(default=1)
    clasico_level: Mapped[int] = mapped_column(default=1)
    # последний сезон, в котором была цель «купить звёздного игрока»
    star_last_season: Mapped[int] = mapped_column(default=0)
