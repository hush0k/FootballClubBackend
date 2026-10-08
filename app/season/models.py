from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Competition(StrEnum):
    LALIGA = "laliga"
    CHAMPIONS_LEAGUE = "champions_league"


class Stage(StrEnum):
    """Стадия турнира. В Ла Лиге всегда LEAGUE, в ЛЧ — общий этап, потом плей-офф."""

    LEAGUE = "league"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    FINAL = "final"


def _competition_column():
    return mapped_column(
        Enum(Competition, name="competition", native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=Competition.LALIGA,
        index=True,
    )


class Standing(Base):
    """Строка турнирной таблицы турнира. team_id = None — наш клуб (его нет в teams).

    Клуб, играющий и в Ла Лиге, и в ЛЧ, имеет по строке в каждой таблице.
    """

    __tablename__ = "season_standings"
    # NULLS NOT DISTINCT: наш клуб (team_id = NULL) тоже не больше одного раза на турнир
    __table_args__ = (
        UniqueConstraint("competition", "team_id", postgresql_nulls_not_distinct=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition: Mapped[Competition] = _competition_column()
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    played: Mapped[int] = mapped_column(default=0)
    wins: Mapped[int] = mapped_column(default=0)
    draws: Mapped[int] = mapped_column(default=0)
    losses: Mapped[int] = mapped_column(default=0)
    goals_for: Mapped[int] = mapped_column(default=0)
    goals_against: Mapped[int] = mapped_column(default=0)
    points: Mapped[int] = mapped_column(default=0)
    # квалификация в ЛЧ по итогам прошлого завершённого сезона (топ-3, только в таблице Ла Лиги)
    champions_league: Mapped[bool] = mapped_column(default=False)


def standing_sort_key(s: Standing):
    # очки → разница мячей → меньше пропущенных → имя
    return -s.points, -(s.goals_for - s.goals_against), s.goals_against, s.name


class SeasonFixture(Base):
    """Матч из расписания текущего сезона. team_id = None — наш клуб.

    round — тур внутри турнира, week — неделя сезона. В одну неделю могут
    пройти тур Ла Лиги и тур ЛЧ. В плей-офф ничьей быть не может —
    победитель определяется серией пенальти (home_penalties / guest_penalties).
    """

    __tablename__ = "season_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition: Mapped[Competition] = _competition_column()
    round: Mapped[int] = mapped_column(index=True)
    week: Mapped[int] = mapped_column(index=True)
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    guest_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    home_goals: Mapped[int | None]
    guest_goals: Mapped[int | None]
    played: Mapped[bool] = mapped_column(default=False)
    stage: Mapped[Stage] = mapped_column(
        Enum(Stage, name="stage", native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        default=Stage.LEAGUE,
        server_default=Stage.LEAGUE.value,
    )
    home_penalties: Mapped[int | None]
    guest_penalties: Mapped[int | None]


class TaskType(StrEnum):
    WINS = "wins"
    POINTS = "points"
    PLACE = "place"
    GOALS = "goals"
    CHAMPIONS_LEAGUE = "champions_league"


class SeasonTask(Base):
    __tablename__ = "season_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, name="task_type", native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])
    )
    target: Mapped[int]
    reward: Mapped[float]
    # выбрана ли задача на текущий сезон (логику выбора добавим позже)
    is_active: Mapped[bool] = mapped_column(default=False)
    is_completed: Mapped[bool] = mapped_column(default=False)
