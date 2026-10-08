from datetime import date as date_
from enum import StrEnum

from pydantic import BaseModel, Field

from app.team.schemas import TeamRead


class MatchOutcome(StrEnum):
    REAL = "real"
    DRAW = "draw"
    ENEMY = "enemy"


class Side(StrEnum):
    HOME = "home"
    GUEST = "guest"


class TeamPower(BaseModel):
    power: float
    starters: int


class WinChance(BaseModel):
    power: float
    enemy_power: int
    win: float
    draw: float
    lose: float


class MatchRequest(BaseModel):
    enemy_id: int
    side: Side = Side.HOME
    date: date_ | None = None


class MatchResult(BaseModel):
    enemy: TeamRead
    real_goals: int = Field(ge=0)
    enemy_goals: int = Field(ge=0)
    result: MatchOutcome
    side: Side | None = None
    date: date_ | None = None
