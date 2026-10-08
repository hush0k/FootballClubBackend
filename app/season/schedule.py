"""Генерация расписания сезона для Ла Лиги и ЛЧ.

Участник — team_id, наш клуб — None.

Ла Лига — двухкруговой турнир: каждый круг n-1 туров, в каждом туре каждая
команда играет ровно один раз, ни одна пара не повторяется. Второй круг —
те же пары с обменом хозяев и гостей. Тур r идёт в неделю r.

ЛЧ — общий этап из 5 туров (у каждого 5 разных соперников, общая таблица),
затем плей-офф на выбывание: лучшие клубы таблицы, 1-й с последним, 2-й
с предпоследним и т. д. Туры ЛЧ раскидываются по неделям сезона, поэтому
в некоторые недели клуб играет два матча — по одному в каждом турнире.
Пары следующего раунда плей-офф создаются, когда доигран предыдущий.
"""
import random
from collections.abc import Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.season.models import Competition, SeasonFixture, Stage, Standing
from app.team.models import League, Team

Participant = int | None
Pair = tuple[Participant, Participant]  # (хозяин, гость)

_BYE = object()  # пустое место при нечётном числе команд — эта команда тур пропускает

CHAMPIONS_LEAGUE_SPANISH_SPOTS = 3  # сколько клубов Ла Лиги попадает в ЛЧ
CHAMPIONS_LEAGUE_LEAGUE_ROUNDS = 5  # матчей у каждого клуба в общем этапе ЛЧ
CHAMPIONS_LEAGUE_MAX_PLAYOFF = 16  # больше клубов в плей-офф не выходит
# общий этап ЛЧ идёт в первые 2/3 сезона, остаток — под плей-офф
LEAGUE_PHASE_SHARE = 2 / 3

PLAYOFF_STAGES = {16: Stage.ROUND_OF_16, 8: Stage.QUARTER_FINAL, 4: Stage.SEMI_FINAL, 2: Stage.FINAL}


def round_robin(participants: Sequence[Participant], rng: random.Random | None = None) -> list[list[Pair]]:
    """Один круг методом «карусели». Без rng — детерминированный (дефолтный) порядок."""
    slots: list = list(participants)
    if rng is not None:
        rng.shuffle(slots)
    if len(slots) % 2:
        slots.append(_BYE)
    n = len(slots)

    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = slots[i], slots[n - 1 - i]
            if a is _BYE or b is _BYE:
                continue
            swap = rng.random() < 0.5 if rng is not None else (r + i) % 2 == 1
            pairs.append((b, a) if swap else (a, b))
        rounds.append(pairs)
        # первый слот стоит на месте, остальные сдвигаются по кругу
        slots = [slots[0], slots[-1], *slots[1:-1]]

    if rng is not None:
        rng.shuffle(rounds)
    return rounds


def double_round_robin(participants: Sequence[Participant], rng: random.Random | None = None) -> list[list[Pair]]:
    first = round_robin(participants, rng)
    second = [[(guest, home) for home, guest in pairs] for pairs in first]
    if rng is not None:
        rng.shuffle(second)
    return first + second


def spread_weeks(rounds: int, weeks: int, rng: random.Random | None = None) -> list[int]:
    """Номера недель (по возрастанию) для туров турнира: каждый тур — в свою неделю.

    Без rng — равномерно по сезону, с rng — случайные недели.
    """
    if rounds >= weeks:
        return list(range(1, rounds + 1))
    if rng is not None:
        return sorted(rng.sample(range(1, weeks + 1), rounds))
    if rounds == 1:
        return [1]
    return [1 + round(i * (weeks - 1) / (rounds - 1)) for i in range(rounds)]


def league_phase(participants: Sequence[Participant], rng: random.Random | None = None) -> list[list[Pair]]:
    """Общий этап ЛЧ: первые туры круговой «карусели» — у каждого разные соперники, без повторов."""
    return round_robin(participants, rng)[:CHAMPIONS_LEAGUE_LEAGUE_ROUNDS]


def playoff_size(participants: int) -> int:
    """Сколько клубов выходит в плей-офф: степень двойки, не больше половины участников."""
    size = 2
    while size * 2 <= min(participants // 2, CHAMPIONS_LEAGUE_MAX_PLAYOFF):
        size *= 2
    return size


def playoff_rounds(participants: int) -> int:
    return playoff_size(participants).bit_length() - 1  # 4 клуба → 2 раунда, 8 → 3, 16 → 4


def bracket_order(size: int) -> list[int]:
    """Посев сетки: [1, 8, 4, 5, 2, 7, 3, 6] для 8 — 1-й и 2-й могут встретиться только в финале."""
    order = [1]
    while len(order) < size:
        total = len(order) * 2 + 1
        order = [seed for s in order for seed in (s, total - s)]
    return order


def seed_playoff(ranked: Sequence[Participant]) -> list[Pair]:
    """Первый раунд плей-офф по местам в таблице общего этапа. Хозяин — клуб, занявший место выше."""
    order = bracket_order(len(ranked))
    return [(ranked[order[i] - 1], ranked[order[i + 1] - 1]) for i in range(0, len(order), 2)]


def next_playoff_pairs(winners: Sequence[Participant]) -> list[Pair]:
    """Победители соседних пар сетки играют друг с другом."""
    return [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]


def next_playoff_week(last_week: int, season_weeks: int, rounds_left: int) -> int:
    """Неделя следующего раунда плей-офф: оставшиеся раунды равномерно до конца сезона."""
    return last_week + max(1, (season_weeks - last_week) // rounds_left)


def fixture_winner(fixture: SeasonFixture) -> int | None:
    """Прошедший дальше клуб сыгранного матча плей-офф (None — наш клуб): по голам, при ничьей — по пенальти."""
    home_won = (fixture.home_goals, fixture.home_penalties or 0) > (fixture.guest_goals, fixture.guest_penalties or 0)
    return fixture.home_team_id if home_won else fixture.guest_team_id


# --- хранение в БД ---


async def get_laliga_participants(db: AsyncSession) -> list[Participant]:
    team_ids = await db.scalars(select(Team.id).where(Team.league == League.LALIGA).order_by(Team.id))
    return [None, *team_ids]


async def get_champions_league_participants(db: AsyncSession) -> list[Participant]:
    """Топ-3 Ла Лиги прошлого сезона + иностранные клубы.

    В первом сезоне квалификации ещё не было — берём наш клуб и 2 сильнейших клуба Ла Лиги.
    Число участников должно быть чётным (в каждом туре играют все), поэтому
    при нечётном самый слабый иностранный клуб в ЛЧ не попадает.
    """
    spanish = list(await db.scalars(
        select(Standing.team_id).where(Standing.competition == Competition.LALIGA, Standing.champions_league)
    ))
    if not spanish:
        strongest = await db.scalars(
            select(Team.id).where(Team.league == League.LALIGA)
            .order_by(Team.power.desc(), Team.id).limit(CHAMPIONS_LEAGUE_SPANISH_SPOTS - 1)
        )
        spanish = [None, *strongest]
    foreign = list(await db.scalars(
        select(Team.id).where(Team.league == League.FOREIGN).order_by(Team.power.desc(), Team.id)
    ))
    if (len(spanish) + len(foreign)) % 2:
        foreign.pop()
    return [*spanish, *foreign]


async def generate_schedule(db: AsyncSession, rng: random.Random | None = None) -> None:
    """Перезаписывает расписание обоих турниров. rng=None — дефолтное расписание первого сезона."""
    await db.execute(delete(SeasonFixture))

    laliga = double_round_robin(await get_laliga_participants(db), rng)
    for number, pairs in enumerate(laliga, start=1):
        for home, guest in pairs:
            db.add(SeasonFixture(
                competition=Competition.LALIGA, round=number, week=number, home_team_id=home, guest_team_id=guest,
            ))

    # туры общего этапа ЛЧ; недели плей-офф назначаются, когда он будет доигран
    champions = league_phase(await get_champions_league_participants(db), rng)
    weeks = spread_weeks(len(champions), int(len(laliga) * LEAGUE_PHASE_SHARE), rng)
    for number, (week, pairs) in enumerate(zip(weeks, champions), start=1):
        for home, guest in pairs:
            db.add(SeasonFixture(
                competition=Competition.CHAMPIONS_LEAGUE, round=number, week=week,
                home_team_id=home, guest_team_id=guest,
            ))
    await db.flush()


async def add_playoff_round(
    db: AsyncSession, pairs: Sequence[Pair], stage: Stage, round_: int, week: int,
) -> None:
    for home, guest in pairs:
        db.add(SeasonFixture(
            competition=Competition.CHAMPIONS_LEAGUE, stage=stage, round=round_, week=week,
            home_team_id=home, guest_team_id=guest,
        ))
    await db.flush()


async def get_season_weeks(db: AsyncSession) -> int:
    """Длина сезона — число недель Ла Лиги."""
    return await db.scalar(
        select(func.max(SeasonFixture.week)).where(SeasonFixture.competition == Competition.LALIGA)
    ) or 0


async def get_competition_fixtures(db: AsyncSession, competition: Competition) -> list[SeasonFixture]:
    result = await db.scalars(
        select(SeasonFixture).where(SeasonFixture.competition == competition)
        .order_by(SeasonFixture.round, SeasonFixture.id)
    )
    return list(result)


async def ensure_schedule(db: AsyncSession) -> None:
    # первый запуск: расписания ещё нет — создаём дефолтное
    if await db.scalar(select(SeasonFixture.id).limit(1)) is None:
        await generate_schedule(db)
        return
    # расписание создано до появления ЛЧ: досоздаём его, только если сезон ещё не начат
    has_champions = await db.scalar(
        select(SeasonFixture.id).where(SeasonFixture.competition == Competition.CHAMPIONS_LEAGUE).limit(1)
    )
    started = await db.scalar(select(SeasonFixture.id).where(SeasonFixture.played).limit(1))
    if has_champions is None and started is None:
        await generate_schedule(db)


async def get_current_week(db: AsyncSession) -> int | None:
    """Ближайшая неделя с несыгранными матчами, None — сезон доигран."""
    return await db.scalar(select(func.min(SeasonFixture.week)).where(SeasonFixture.played.is_(False)))


async def get_week_fixtures(db: AsyncSession, week: int) -> list[SeasonFixture]:
    result = await db.scalars(select(SeasonFixture).where(SeasonFixture.week == week).order_by(SeasonFixture.id))
    return list(result)


async def get_fixture_participants(db: AsyncSession, competition: Competition) -> set[Participant]:
    """Все клубы, у которых есть матчи общего этапа турнира в текущем расписании."""
    rows = await db.execute(
        select(SeasonFixture.home_team_id, SeasonFixture.guest_team_id)
        .where(SeasonFixture.competition == competition, SeasonFixture.stage == Stage.LEAGUE)
    )
    return {team_id for row in rows for team_id in row}


async def count_own_fixtures(db: AsyncSession, competition: Competition = Competition.LALIGA) -> int:
    return await db.scalar(
        select(func.count(SeasonFixture.id)).where(
            SeasonFixture.competition == competition,
            or_(SeasonFixture.home_team_id.is_(None), SeasonFixture.guest_team_id.is_(None)),
        )
    )
