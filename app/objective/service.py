"""Цели клуба на сезон.

Ла Лига, ЛЧ и Эль Класико — лестницы уровней: выполнил цель — в следующем
сезоне уровень выше (цель сложнее, награда больше), провалил — штраф и
уровень ниже. Цель ЛЧ появляется в каждом сезоне, где клуб играет в ЛЧ.
«Омолодить состав» — когда средний возраст состава больше
30 лет, «купить звёздного игрока» — в случайный сезон, но не реже раза в 6 сезонов.

Награды и штрафы начисляются в бюджет в конце сезона (evaluate_season).
"""
import random

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance import service as finance_service
from app.objective.models import ClubObjective, ObjectiveState, ObjectiveStatus, ObjectiveType
from app.objective.schemas import SquadAge
from app.player.models import Player, PlayerStatus
from app.season import schedule
from app.season.models import Competition, SeasonFixture, Stage, Standing, standing_sort_key
from app.team.models import Team

MAX_SQUAD_AGE = 30  # выше — появляется цель «омолодить состав»
STAR_PLAYER_POWER = 88  # звезда — рейтинг выше этого
STAR_PLAYER_CHANCE = 0.25  # шанс цели «купить звезду» в обычный сезон
STAR_PLAYER_MAX_GAP = 6  # и не реже раза в столько сезонов
CLASICO_RIVAL = "Barcelona"

# уровень → (target, награда, штраф, условие)
LALIGA_LADDER = {
    1: (10, 20, 30, "Войти в топ-10 Ла Лиги"),
    2: (5, 25, 30, "Войти в топ-5 Ла Лиги"),
    3: (3, 35, 30, "Войти в топ-3 Ла Лиги"),
    4: (1, 50, 30, "Стать чемпионом Ла Лиги"),
}

# progress цели ЛЧ — глубина стадии, до которой дошёл клуб
STAGE_DEPTH = {Stage.LEAGUE: 0, Stage.ROUND_OF_16: 1, Stage.QUARTER_FINAL: 2, Stage.SEMI_FINAL: 3, Stage.FINAL: 4}
CHAMPIONS_LEAGUE_WON = 5
CHAMPIONS_LEAGUE_LADDER = {
    1: (1, 25, 20, "Выйти в плей-офф Лиги чемпионов"),
    2: (3, 40, 25, "Дойти до полуфинала Лиги чемпионов"),
    3: (CHAMPIONS_LEAGUE_WON, 60, 30, "Выиграть Лигу чемпионов"),
}

# progress Эль Класико — очки в матчах Ла Лиги с Барселоной: ничья 1, победа 3
CLASICO_LADDER = {
    1: (1, 10, 10, "Эль Класико: сыграть вничью хотя бы один матч с Барселоной"),
    2: (3, 15, 10, "Эль Класико: выиграть один матч у Барселоны"),
    3: (4, 20, 15, "Эль Класико: одна победа и одна ничья с Барселоной"),
    4: (6, 30, 20, "Эль Класико: выиграть оба матча у Барселоны"),
}

REJUVENATE = (MAX_SQUAD_AGE, 15, 15, f"Омолодить состав: средний возраст не больше {MAX_SQUAD_AGE} лет")
STAR_PLAYER = (STAR_PLAYER_POWER + 1, 30, 20, f"Купить звёздного игрока с рейтингом выше {STAR_PLAYER_POWER}")

LADDERS = {
    ObjectiveType.LALIGA_PLACE: ("laliga_level", LALIGA_LADDER),
    ObjectiveType.CHAMPIONS_LEAGUE: ("champions_league_level", CHAMPIONS_LEAGUE_LADDER),
    ObjectiveType.EL_CLASICO: ("clasico_level", CLASICO_LADDER),
}


async def get_state(db: AsyncSession) -> ObjectiveState:
    state = await db.scalar(select(ObjectiveState).limit(1))
    if state is None:
        state = ObjectiveState()
        db.add(state)
        await db.flush()
    return state


async def get_season_objectives(db: AsyncSession, season: int) -> list[ClubObjective]:
    result = await db.scalars(select(ClubObjective).where(ClubObjective.season == season).order_by(ClubObjective.id))
    return list(result)


async def get_all_objectives(db: AsyncSession) -> list[ClubObjective]:
    result = await db.scalars(select(ClubObjective).order_by(ClubObjective.season, ClubObjective.id))
    return list(result)


def _objective(season: int, type_: ObjectiveType, level: int | None, spec: tuple) -> ClubObjective:
    target, reward, penalty, condition = spec
    return ClubObjective(
        season=season, type=type_, level=level, target=target, reward=reward, penalty=penalty,
        condition=condition, progress=0, status=ObjectiveStatus.ACTIVE,
    )


# --- прогресс ---


async def get_squad_age(db: AsyncSession) -> SquadAge:
    avg, count = (await db.execute(
        select(func.avg(Player.age), func.count(Player.id)).where(Player.status == PlayerStatus.SQUAD)
    )).one()
    average = round(float(avg or 0), 1)
    return SquadAge(
        average_age=average, players=count, limit=MAX_SQUAD_AGE, needs_rejuvenation=average > MAX_SQUAD_AGE,
    )


async def _laliga_place(db: AsyncSession) -> int:
    standings = sorted(
        await db.scalars(select(Standing).where(Standing.competition == Competition.LALIGA)), key=standing_sort_key,
    )
    for place, s in enumerate(standings, start=1):
        if s.team_id is None:
            return place
    return len(standings) + 1


def _is_own(fixture: SeasonFixture) -> bool:
    return fixture.home_team_id is None or fixture.guest_team_id is None


async def _champions_league_depth(db: AsyncSession) -> int:
    depth = 0
    for fixture in await schedule.get_competition_fixtures(db, Competition.CHAMPIONS_LEAGUE):
        if not _is_own(fixture):
            continue
        depth = max(depth, STAGE_DEPTH[fixture.stage])
        if fixture.stage == Stage.FINAL and fixture.played and schedule.fixture_winner(fixture) is None:
            depth = CHAMPIONS_LEAGUE_WON
    return depth


async def _rival_id(db: AsyncSession) -> int | None:
    return await db.scalar(select(Team.id).where(Team.name == CLASICO_RIVAL))


async def _clasico_points(db: AsyncSession) -> int:
    rival = await _rival_id(db)
    fixtures = await db.scalars(select(SeasonFixture).where(
        SeasonFixture.competition == Competition.LALIGA,
        SeasonFixture.played,
        or_(
            (SeasonFixture.home_team_id.is_(None)) & (SeasonFixture.guest_team_id == rival),
            (SeasonFixture.guest_team_id.is_(None)) & (SeasonFixture.home_team_id == rival),
        ),
    ))
    points = 0
    for f in fixtures:
        own, other = (f.home_goals, f.guest_goals) if f.home_team_id is None else (f.guest_goals, f.home_goals)
        points += 3 if own > other else 1 if own == other else 0
    return points


async def refresh_progress(db: AsyncSession, objectives: list[ClubObjective]) -> None:
    """Пересчитывает прогресс активных целей. Звёздного игрока считает on_player_bought."""
    for o in objectives:
        if o.status != ObjectiveStatus.ACTIVE:
            continue
        if o.type == ObjectiveType.LALIGA_PLACE:
            o.progress = await _laliga_place(db)
        elif o.type == ObjectiveType.CHAMPIONS_LEAGUE:
            o.progress = await _champions_league_depth(db)
        elif o.type == ObjectiveType.EL_CLASICO:
            o.progress = await _clasico_points(db)
        elif o.type == ObjectiveType.REJUVENATE:
            o.progress = (await get_squad_age(db)).average_age


# --- жизненный цикл сезона ---


async def ensure_objectives(db: AsyncSession, rng: random.Random = random) -> list[ClubObjective]:
    """Создаёт цели текущего сезона, если их ещё нет, и обновляет прогресс."""
    state = await get_state(db)
    objectives = await get_season_objectives(db, state.season)
    if not objectives:
        season = state.season
        objectives.append(_objective(
            season, ObjectiveType.LALIGA_PLACE, state.laliga_level, LALIGA_LADDER[state.laliga_level],
        ))

        if await _plays_champions_league(db):
            objectives.append(_champions_league_objective(state))

        if await _rival_id(db) is not None:
            objectives.append(_objective(
                season, ObjectiveType.EL_CLASICO, state.clasico_level, CLASICO_LADDER[state.clasico_level],
            ))

        if (await get_squad_age(db)).needs_rejuvenation:
            objectives.append(_objective(season, ObjectiveType.REJUVENATE, None, REJUVENATE))

        if rng.random() < STAR_PLAYER_CHANCE or season - state.star_last_season >= STAR_PLAYER_MAX_GAP:
            objectives.append(_objective(season, ObjectiveType.STAR_PLAYER, None, STAR_PLAYER))
            state.star_last_season = season

        db.add_all(objectives)
        await db.flush()
    elif (
        not state.finished
        and all(o.type != ObjectiveType.CHAMPIONS_LEAGUE for o in objectives)
        and await _plays_champions_league(db)
    ):
        # цели сезона созданы раньше, когда цель ЛЧ ещё требовала топ-3 лестницы Ла Лиги
        objective = _champions_league_objective(state)
        db.add(objective)
        await db.flush()
        objectives.append(objective)
    await refresh_progress(db, objectives)
    return objectives


async def _plays_champions_league(db: AsyncSession) -> bool:
    await schedule.ensure_schedule(db)
    return None in await schedule.get_fixture_participants(db, Competition.CHAMPIONS_LEAGUE)


def _champions_league_objective(state: ObjectiveState) -> ClubObjective:
    level = state.champions_league_level
    return _objective(state.season, ObjectiveType.CHAMPIONS_LEAGUE, level, CHAMPIONS_LEAGUE_LADDER[level])


async def evaluate_season(db: AsyncSession) -> list[ClubObjective]:
    """Конец сезона: награда за выполненные цели, штраф за проваленные, сдвиг уровней. Без commit."""
    state = await get_state(db)
    objectives = await ensure_objectives(db)
    for o in objectives:
        if o.status != ObjectiveStatus.ACTIVE:
            continue
        success = o.achieved
        o.status = ObjectiveStatus.COMPLETED if success else ObjectiveStatus.FAILED
        await finance_service.apply_budget_change(db, o.reward if success else -o.penalty)

        if o.type in LADDERS:
            attr, ladder = LADDERS[o.type]
            level = getattr(state, attr)
            setattr(state, attr, min(level + 1, max(ladder)) if success else max(level - 1, 1))
    return objectives


async def start_new_season(db: AsyncSession, rng: random.Random = random) -> list[ClubObjective]:
    """Новый сезон после завершённого: номер сезона +1, все игроки стареют на год, новые цели. Без commit."""
    state = await get_state(db)
    if state.finished:
        state.season += 1
        state.finished = False
        await db.execute(update(Player).values(age=Player.age + 1))
    return await ensure_objectives(db, rng)


async def on_player_bought(db: AsyncSession, player: Player) -> None:
    """Покупка звезды засчитывается в активную цель текущего сезона. Без commit."""
    if player.power <= STAR_PLAYER_POWER:
        return
    state = await get_state(db)
    objective = await db.scalar(select(ClubObjective).where(
        ClubObjective.season == state.season,
        ClubObjective.type == ObjectiveType.STAR_PLAYER,
        ClubObjective.status == ObjectiveStatus.ACTIVE,
    ))
    if objective is not None:
        objective.progress = max(objective.progress, player.power)


async def get_current(db: AsyncSession) -> tuple[ObjectiveState, list[ClubObjective]]:
    objectives = await ensure_objectives(db)
    state = await get_state(db)
    await db.commit()
    return state, objectives


async def reset(db: AsyncSession) -> tuple[ObjectiveState, list[ClubObjective]]:
    """Удаляет все цели и уровни — игра целей начинается с 1-го сезона. Возраст игроков не откатывается."""
    await db.execute(delete(ClubObjective))
    await db.execute(delete(ObjectiveState))
    await db.flush()
    return await get_current(db)
