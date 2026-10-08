from datetime import date as date_

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.game_engine.schemas import MatchResult, Side
from app.season.models import Competition, Stage, TaskType
from app.team.schemas import TeamRead


class StandingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int = 0
    competition: Competition
    team_id: int | None
    name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    points: int
    champions_league: bool

    @computed_field
    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @computed_field
    @property
    def is_own_club(self) -> bool:
        return self.team_id is None


class FixtureResult(BaseModel):
    home: str
    guest: str
    home_goals: int
    guest_goals: int
    # серия пенальти — только после ничьей в плей-офф
    home_penalties: int | None = None
    guest_penalties: int | None = None


class PenaltyScore(BaseModel):
    real: int
    enemy: int


class RoundRequest(BaseModel):
    # соперник и сторона берутся из расписания
    date: date_ | None = None


class CompetitionRoundResult(BaseModel):
    competition: Competition
    stage: Stage
    round: int
    # None — наш клуб не играет в этом туре (нечётное число команд, не участвуем в ЛЧ или вылетели)
    match: MatchResult | None
    # серия пенальти нашего матча плей-офф, если основное время закончилось вничью
    penalties: PenaltyScore | None = None
    other_matches: list[FixtureResult]
    standings: list[StandingRead]


class RoundResult(BaseModel):
    """Итог недели: тур Ла Лиги и, если он стоит на эту неделю, тур ЛЧ."""

    week: int
    results: list[CompetitionRoundResult]


class ScheduledMatch(BaseModel):
    home_team_id: int | None
    guest_team_id: int | None
    home: str
    guest: str
    home_goals: int | None
    guest_goals: int | None
    home_penalties: int | None
    guest_penalties: int | None
    played: bool
    # прошедший дальше клуб матча плей-офф (после игры); в общем этапе — None
    winner: str | None = None


class ScheduleRound(BaseModel):
    competition: Competition
    stage: Stage
    round: int
    week: int
    matches: list[ScheduledMatch]


class PlayoffBracket(BaseModel):
    # сколько клубов из таблицы общего этапа выходит в плей-офф
    qualified: int
    rounds: list[ScheduleRound]
    # победитель финала, None — ЛЧ ещё не доиграна
    champion: str | None


class NextMatch(BaseModel):
    competition: Competition
    stage: Stage
    round: int
    week: int
    enemy: TeamRead
    side: Side


class SeasonTaskBase(BaseModel):
    title: str = Field(max_length=100)
    description: str = Field(max_length=255)
    type: TaskType
    target: int = Field(ge=0)
    reward: float = Field(ge=0)
    is_active: bool = False
    is_completed: bool = False


class SeasonTaskCreate(SeasonTaskBase):
    pass


class SeasonTaskUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    type: TaskType | None = None
    target: int | None = Field(default=None, ge=0)
    reward: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_completed: bool | None = None


class SeasonTaskRead(SeasonTaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
