# Импортируй сюда модели всех модулей, чтобы Alembic видел их в Base.metadata.
from app.core.database import Base  # noqa: F401
from app.team.models import Team  # noqa: F401
from app.player.models import Player  # noqa: F401
from app.coach.models import Coach  # noqa: F401
from app.stadium.models import StadiumUpgrade  # noqa: F401
from app.season.models import SeasonFixture, SeasonTask, Standing  # noqa: F401
from app.finance.models import ClubFinance  # noqa: F401
from app.objective.models import ClubObjective, ObjectiveState  # noqa: F401
