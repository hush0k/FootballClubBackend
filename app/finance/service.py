import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach.service import get_total_salary as get_staff_salary
from app.finance.models import ClubFinance
from app.finance.schemas import FinanceRead, FinanceSummary, SeasonStatus
from app.game_engine.schemas import MatchOutcome
from app.player.models import Player, PlayerStatus
from app.season import schedule
from app.season.models import Competition, Standing
from app.stadium.service import get_bonuses

# млн в общий бюджет за наш матч (умножается на бонус дохода стадиона)
MATCH_REWARDS = {
    Competition.LALIGA: {MatchOutcome.REAL: 7.0, MatchOutcome.DRAW: 4.0},
    Competition.CHAMPIONS_LEAGUE: {MatchOutcome.REAL: 10.0, MatchOutcome.DRAW: 6.0},
}
LALIGA_TITLE_BONUS = 60  # млн за победу в Ла Лиге
CHAMPIONS_LEAGUE_TITLE_BONUS = 110  # млн за победу в ЛЧ
START_FANS = 500
START_SALARY_FUND = 350
FANS_PER_BONUS = 10  # каждые 10 млн новых болельщиков...
SALARY_FUND_BONUS = 5  # ...+5 млн к фонду зарплат
FANS_PENALTY_STEP = 10  # каждые 10 млн болельщиков ниже 500...
FANS_PENALTY = 10  # ...-10 млн от фонда зарплат и трансферного бюджета
SALE_TRANSFER_SHARE = 0.6  # 60% цены проданного игрока идёт в трансферный бюджет
LOSE_LOSSES = 12  # больше — сезон провален
WIN_LOSSES = 5  # меньше — сезон выигран

BASE_FANS_GROWTH = {
    MatchOutcome.REAL: 1.2,
    MatchOutcome.DRAW: 0.3,
    MatchOutcome.ENEMY: -0.9,
}


def round1(value: float) -> float:
    return round(value, 1)


# --- чтение ---


async def get_finance(db: AsyncSession) -> ClubFinance:
    finance = await db.scalar(select(ClubFinance).limit(1))
    if finance is None:
        finance = ClubFinance()
        db.add(finance)
        await db.flush()
    return finance


async def get_all_salary(db: AsyncSession) -> float:
    squad = await db.scalar(
        select(func.coalesce(func.sum(Player.salary), 0.0)).where(Player.status == PlayerStatus.SQUAD)
    )
    return squad + await get_staff_salary(db)


def calc_fan_penalty(fans: float) -> float:
    steps = math.floor(round1(max(0, START_FANS - fans)) / FANS_PENALTY_STEP)
    return steps * FANS_PENALTY


def get_season_status(played: int, season_rounds: int, losses: int) -> SeasonStatus:
    if played < season_rounds:
        return SeasonStatus.IN_PROGRESS
    if losses > LOSE_LOSSES:
        return SeasonStatus.LOSE
    if losses < WIN_LOSSES:
        return SeasonStatus.WIN
    return SeasonStatus.FINISHED


async def get_summary(db: AsyncSession) -> FinanceSummary:
    finance = await get_finance(db)
    all_salary = await get_all_salary(db)
    bonuses = await get_bonuses(db)
    penalty = calc_fan_penalty(finance.fans)
    own = await db.scalar(
        select(Standing).where(Standing.competition == Competition.LALIGA, Standing.team_id.is_(None))
    )
    played, losses = (own.played, own.losses) if own else (0, 0)
    # длина сезона = число наших матчей Ла Лиги в расписании (14 клубов → 26), матчи ЛЧ не считаются
    await schedule.ensure_schedule(db)
    season_rounds = await schedule.count_own_fixtures(db)

    return FinanceSummary(
        **FinanceRead.model_validate(finance).model_dump(),
        all_salary=round1(all_salary),
        available_budget=round1(finance.annual_budget - all_salary - finance.spent),
        income_bonus=bonuses.income,
        fans_bonus=bonuses.fans,
        win_reward=round1(MATCH_REWARDS[Competition.LALIGA][MatchOutcome.REAL] * bonuses.income),
        draw_reward=round1(MATCH_REWARDS[Competition.LALIGA][MatchOutcome.DRAW] * bonuses.income),
        champions_league_win_reward=round1(
            MATCH_REWARDS[Competition.CHAMPIONS_LEAGUE][MatchOutcome.REAL] * bonuses.income
        ),
        champions_league_draw_reward=round1(
            MATCH_REWARDS[Competition.CHAMPIONS_LEAGUE][MatchOutcome.DRAW] * bonuses.income
        ),
        fan_penalty=penalty,
        effective_salary_fund=finance.salary_fund - penalty,
        effective_transfer_budget=max(0, round1(finance.transfer_budget - penalty)),
        effective_transfer_left=max(0, round1(finance.transfer_budget_left - penalty)),
        matches_played=played,
        season_rounds=season_rounds,
        season_status=get_season_status(played, season_rounds, losses),
    )


# --- проверки (возвращают причину отказа или None) ---


async def check_can_buy(db: AsyncSession, player: Player) -> str | None:
    s = await get_summary(db)
    if s.effective_transfer_left < player.price:
        return "Мало трансферного бюджета"
    if s.all_salary + player.salary > s.effective_salary_fund:
        return "Превышен фонд зарплат"
    if s.available_budget < player.price + player.salary:
        return "Мало свободных средств"
    return None


async def check_can_spend(db: AsyncSession, price: float) -> str | None:
    s = await get_summary(db)
    if s.available_budget < price:
        return "Мало свободных средств"
    return None


# --- изменения (без commit — коммитит вызывающий сервис вместе со своими изменениями) ---


async def apply_purchase(db: AsyncSession, price: float) -> None:
    finance = await get_finance(db)
    finance.spent = round1(finance.spent + price)
    finance.transfer_budget_left = round1(finance.transfer_budget_left - price)


async def apply_sale(db: AsyncSession, price: float) -> float:
    """Возвращает бонус в трансферный бюджет."""
    finance = await get_finance(db)
    bonus = round1(price * SALE_TRANSFER_SHARE)
    finance.annual_budget = round1(finance.annual_budget + price)
    finance.transfer_budget = round1(finance.transfer_budget + bonus)
    finance.transfer_budget_left = round1(finance.transfer_budget_left + bonus)
    return bonus


async def apply_spending(db: AsyncSession, price: float) -> None:
    finance = await get_finance(db)
    finance.spent = round1(finance.spent + price)


async def apply_budget_change(db: AsyncSession, amount: float) -> None:
    """Бонус (amount > 0) или штраф (amount < 0) в общий бюджет: трофеи, цели клуба."""
    finance = await get_finance(db)
    finance.annual_budget = round1(finance.annual_budget + amount)


async def apply_week_results(db: AsyncSession, outcomes: list[tuple[Competition, MatchOutcome]]) -> None:
    """Итоги наших матчей за неделю (0, 1 или 2 — Ла Лига и ЛЧ). Неделя сдвигается один раз."""
    finance = await get_finance(db)
    if outcomes:
        bonuses = await get_bonuses(db)
        week_growth = 0.0
        for competition, outcome in outcomes:
            base = BASE_FANS_GROWTH[outcome]
            # бонус стадиона усиливает только рост, падение не смягчает
            growth = base * bonuses.fans if base > 0 else base
            finance.fans = round1(finance.fans + growth)
            week_growth += growth
            reward = MATCH_REWARDS[competition].get(outcome, 0)
            finance.annual_budget = round1(finance.annual_budget + reward * bonuses.income)
        finance.fans_growth = round(week_growth, 2)

        # фонд зарплат растёт за болельщиков сверх 500, но никогда не уменьшается
        bonus_steps = math.floor(max(0, finance.fans - START_FANS) / FANS_PER_BONUS)
        finance.salary_fund = max(finance.salary_fund, START_SALARY_FUND + bonus_steps * SALARY_FUND_BONUS)
    finance.week += 1


async def reset_finance(db: AsyncSession) -> FinanceSummary:
    finance = await get_finance(db)
    for column in ClubFinance.__table__.columns:
        if column.name != "id":
            setattr(finance, column.name, column.default.arg)
    await db.commit()
    return await get_summary(db)
