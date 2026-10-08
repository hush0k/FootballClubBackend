import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game_engine import engine
from app.game_engine.schemas import MatchResult, Side, TeamPower, WinChance
from app.player.models import LineUp, Player, PlayerStatus
from app.team.models import League, Team
from app.team.schemas import TeamRead


async def get_starter_powers(db: AsyncSession) -> list[int]:
    result = await db.scalars(
        select(Player.power).where(
            Player.status == PlayerStatus.SQUAD,
            Player.line_up == LineUp.STARTER,
        )
    )
    return list(result)


async def get_team_power(db: AsyncSession) -> TeamPower | None:
    powers = await get_starter_powers(db)
    if not powers:
        return None
    return TeamPower(power=round(engine.get_team_power(powers), 2), starters=len(powers))


def get_win_chance(power: float, enemy: Team) -> WinChance:
    chances = engine.get_chances(power, enemy.power)
    return WinChance(
        power=power,
        enemy_power=enemy.power,
        win=round(chances.win, 4),
        draw=round(chances.draw, 4),
        lose=round(chances.lose, 4),
    )


def simulate_match(
    power: float,
    enemy: Team,
    side: Side | None = None,
    match_date: date | None = None,
    rng: random.Random = random,
) -> MatchResult:
    score = engine.simulate_score(power, enemy.power, rng)
    return MatchResult(
        enemy=TeamRead.model_validate(enemy),
        real_goals=score.real_goals,
        enemy_goals=score.enemy_goals,
        result=score.result,
        side=side,
        date=match_date,
    )


async def last_five_matches(db: AsyncSession, power: float, rng: random.Random = random) -> list[MatchResult]:
    teams = list(await db.scalars(select(Team).where(Team.league == League.LALIGA)))
    return [simulate_match(power, rng.choice(teams), rng=rng) for _ in range(5)] if teams else []
