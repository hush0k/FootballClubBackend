from datetime import date as date_

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.game_engine.schemas import MatchResult, Side
from app.objective.schemas import ObjectiveRead
from app.player.schemas import TrainingResult
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
    # матч пары плей-офф: 1 — первый, 2 — ответный; None — общий этап или финал
    leg: int | None = None
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
    academy: list[TrainingResult] = []  # неделя тренировок воспитанников


class ScheduledMatch(BaseModel):
    home_team_id: int | None
    guest_team_id: int | None
    home: str
    guest: str
    home_goals: int | None
    guest_goals: int | None
    home_penalties: int | None
    guest_penalties: int | None
    # голы по сумме двух встреч — у сыгранного ответного матча пары, иначе None
    home_aggregate: int | None = None
    guest_aggregate: int | None = None
    played: bool
    # прошедший дальше клуб пары плей-офф (после ответного матча или финала); в общем этапе — None
    winner: str | None = None


class ScheduleRound(BaseModel):
    competition: Competition
    stage: Stage
    round: int
    week: int
    # матч пары плей-офф: 1 — первый, 2 — ответный; None — общий этап или финал
    leg: int | None = None
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
    leg: int | None = None
    enemy: TeamRead
    side: Side


class NextWeek(BaseModel):
    """Ближайшая неделя: в ней может быть матч Ла Лиги и матч ЛЧ."""

    week: int
    # наши матчи недели, Ла Лига первой; пусто — у нас в эту неделю матча нет
    matches: list[NextMatch]


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


class SeasonHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    status: str
    laliga_position: int
    laliga_total: int
    laliga_points: int
    laliga_wins: int
    laliga_draws: int
    laliga_losses: int
    champions_league_position: int | None
    champions_league_total: int | None
    champions_league_points: int | None
    champions_league_wins: int | None
    champions_league_draws: int | None
    champions_league_losses: int | None
    playoff_stage: Stage | None
    champions_league_champion: bool
    laliga_earnings: float
    champions_league_earnings: float
    title_bonuses: float
    objectives_earnings: float
    budget: float
    fans: float
    reputation: int
    objectives: list[ObjectiveRead] = []

    @computed_field
    @property
    def total_earnings(self) -> float:
        return round(
            self.laliga_earnings + self.champions_league_earnings + self.title_bonuses + self.objectives_earnings, 1
        )
