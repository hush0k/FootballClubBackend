from pydantic import BaseModel, ConfigDict

from app.objective.models import ObjectiveStatus, ObjectiveType


class ObjectiveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    type: ObjectiveType
    level: int | None
    target: int
    condition: str
    reward: float
    penalty: float
    # место в Ла Лиге / стадия ЛЧ (0 — общий этап … 4 — финал, 5 — победа) /
    # средний возраст / рейтинг купленной звезды / очки в Эль Класико
    progress: float
    status: ObjectiveStatus
    achieved: bool  # выполнено ли условие сейчас


class SeasonObjectives(BaseModel):
    season: int
    finished: bool
    objectives: list[ObjectiveRead]


class SquadAge(BaseModel):
    average_age: float
    players: int
    limit: int
    needs_rejuvenation: bool
