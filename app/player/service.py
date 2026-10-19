import random

from sqlalchemy import Select, case, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance import service as finance_service
from app.objective import service as objective_service
from app.player.models import TRAINING_WEIGHTS, LineUp, Player, PlayerStatus, Position, Training
from app.player.schemas import (
    AcademyRead,
    FilterOption,
    PlayerCreate,
    PlayerFilter,
    PlayerFilterOptions,
    PlayerRank,
    PlayerSale,
    PlayerSort,
    PlayerUpdate,
    PositionGroup,
    Range,
    TrainingResult,
)
from app.player.seed import PLAYERS

# порядок статусов при "Изменить статус": по кругу от глубины к основе
LINE_UP_ORDER = [LineUp.DEPTH, LineUp.BENCH, LineUp.ROTATION, LineUp.STARTER]

# сортировка состава по умолчанию, как во фронте: статус → позиция → сила
LINE_UP_PRIORITY = [LineUp.STARTER, LineUp.ROTATION, LineUp.BENCH, LineUp.DEPTH, LineUp.ACADEMY]
POSITION_PRIORITY = list(Position)  # ВР, ПЗ, ЦЗ, ЛЗ, ОП, ЦП, АП, ПВ, ЛВ, ФР

POSITION_GROUPS = {
    PositionGroup.GK: [Position.GK],
    PositionGroup.DEF: [Position.RB, Position.CB, Position.LB],
    PositionGroup.MID: [Position.DM, Position.CM, Position.AM],
    PositionGroup.ATT: [Position.RW, Position.LW, Position.ST],
}

# рейтинг игрока на маркете: от 88 — «Мировой класс», от 80 — «Основа», ниже — «Резерв»
WORLD_CLASS_POWER = 88
STARTER_POWER = 80
RANK_CONDITIONS = {
    PlayerRank.WORLD_CLASS: Player.power >= WORLD_CLASS_POWER,
    PlayerRank.STARTER: Player.power.between(STARTER_POWER, WORLD_CLASS_POWER - 1),
    PlayerRank.RESERVE: Player.power < STARTER_POWER,
}

# направление «по умолчанию» для каждой сортировки; reverse его переворачивает
SORT_COLUMNS = {
    PlayerSort.POWER: (Player.power, True),
    PlayerSort.PRICE: (Player.price, True),
    PlayerSort.SALARY: (Player.salary, True),
    PlayerSort.AGE: (Player.age, False),
    PlayerSort.NUMBER: (Player.number, False),
    PlayerSort.NAME: (Player.last_name, False),
}


# академия: сумма весов тренировок всех воспитанников не больше 8
ACADEMY_WEIGHT_LIMIT = 8
# сколько % прогресса максимум даёт неделя тренировки (выпадает от 0 до этого числа)
TRAINING_MAX_GAIN = {Training.MODERATE: 10, Training.NORMAL: 20, Training.INTENSIVE: 33}
TRAINING_CYCLE = 3  # раз в 3 недели (матча) прогресс превращается в силу
MAX_POWER_GAIN = 1  # при 100% за цикл игрок получает +1 к силе

# пороги силы, на которых растёт цена: множитель и минимальная цена (млн €) после порога
PRICE_THRESHOLDS = {70: (1.5, 5), 75: (1.5, 10), 80: (2, 20), 85: (2, 40)}

# новый воспитанник: возраст и стартовая сила выпадают случайно
ACADEMY_AGE = (9, 14)
ACADEMY_POWER = (45, 63)

# потенциал ~ нормальное распределение: 80–87 чаще всего (~40%), 95–99 примерно у 5%
POTENTIAL_MEAN = 83.5
POTENTIAL_SD = 7
MAX_POTENTIAL = 99


def generate_potential(power: int, rng: random.Random = random) -> int:
    """Случайный потенциал не ниже текущей силы и не выше 99 (у кого сила уже выше — равен силе)."""
    if power >= MAX_POTENTIAL:
        return power
    for _ in range(100):
        potential = round(rng.gauss(POTENTIAL_MEAN, POTENTIAL_SD))
        if power <= potential <= MAX_POTENTIAL:
            return potential
    return rng.randint(power, MAX_POTENTIAL)  # сила далеко в хвосте распределения


def apply_price_growth(player: Player, old_power: int) -> None:
    """Поднимает цену за каждый пройденный порог силы из (old_power, power]."""
    for threshold, (multiplier, min_price) in PRICE_THRESHOLDS.items():
        if old_power < threshold <= player.power:
            player.price = round(max(player.price * multiplier, min_price), 1)


def check_academy(player: Player | None, line_up: LineUp | None) -> str | None:
    """Причина, по которой игрока нельзя перевести в академию, или None."""
    if line_up != LineUp.ACADEMY or player is None or player.line_up == LineUp.ACADEMY:
        return None
    if player.left_academy:
        return "Игрок уже переведён из академии, вернуть его обратно нельзя"
    return None


def _leave_academy(player: Player) -> None:
    player.left_academy = True
    _reset_training(player)



def _priority(column, values: list) -> case:
    return case({v: i for i, v in enumerate(values)}, value=column, else_=len(values))


def _order_by(f: PlayerFilter) -> list:
    if f.sort == PlayerSort.DEFAULT:
        if f.status == PlayerStatus.MARKET:
            keys = [(Player.power, True)]
        else:
            keys = [
                (_priority(Player.line_up, LINE_UP_PRIORITY), False),
                (_priority(Player.position, POSITION_PRIORITY), False),
                (Player.power, False),
            ]
    else:
        keys = [SORT_COLUMNS[f.sort]]

    order = []
    for column, desc in keys:
        desc ^= f.reverse
        order.append(column.desc().nulls_last() if desc else column.asc().nulls_last())
    order.append(Player.id.desc() if f.reverse else Player.id)  # стабильный порядок при равенстве
    return order


async def _apply_filters(db: AsyncSession, query: Select, f: PlayerFilter) -> Select:
    if f.status is not None:
        query = query.where(Player.status == f.status)
    if f.line_up:
        query = query.where(Player.line_up.in_(f.line_up))
    if f.position:
        query = query.where(Player.position.in_(f.position))
    if f.group:
        query = query.where(Player.position.in_([p for g in f.group for p in POSITION_GROUPS[g]]))
    if f.rank:
        query = query.where(or_(*(RANK_CONDITIONS[r] for r in f.rank)))
    if f.club:
        query = query.where(Player.club.in_(f.club))
    if f.league:
        query = query.where(Player.league.in_(f.league))
    if f.nation:
        query = query.where(Player.nation.in_(f.nation))
    if f.search:
        pattern = f"%{f.search.strip()}%"
        # «Килиан Мбаппе» и «Мбаппе Килиан» — порядок имени и фамилии не важен
        query = query.where(or_(
            (Player.name + " " + Player.last_name).ilike(pattern),
            (Player.last_name + " " + Player.name).ilike(pattern),
            Player.club.ilike(pattern),
        ))

    for column, low, high in (
        (Player.power, f.min_power, f.max_power),
        (Player.price, f.min_price, f.max_price),
        (Player.salary, f.min_salary, f.max_salary),
        (Player.age, f.min_age, f.max_age),
    ):
        if low is not None:
            query = query.where(column >= low)
        if high is not None:
            query = query.where(column <= high)

    if f.affordable:
        # те же условия, что в finance_service.check_can_buy
        s = await finance_service.get_summary(db)
        query = query.where(
            Player.status == PlayerStatus.MARKET,
            Player.price <= s.effective_transfer_left,
            Player.salary <= s.effective_salary_fund - s.all_salary,
            Player.price + Player.salary <= s.available_budget,
        )
    return query


async def get_players(db: AsyncSession, f: PlayerFilter | None = None) -> tuple[list[Player], int]:
    """Игроки по фильтрам и общее число найденных (без учёта limit/offset)."""
    f = f or PlayerFilter()
    query = await _apply_filters(db, select(Player), f)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    query = query.order_by(*_order_by(f)).offset(f.offset)
    if f.limit is not None:
        query = query.limit(f.limit)
    return list(await db.scalars(query)), total


def _rank_of(power: int) -> PlayerRank:
    if power >= WORLD_CLASS_POWER:
        return PlayerRank.WORLD_CLASS
    if power >= STARTER_POWER:
        return PlayerRank.STARTER
    return PlayerRank.RESERVE


def _options(values) -> list[FilterOption]:
    counts: dict[str, int] = {}
    for v in values:
        if v is not None:
            counts[str(v)] = counts.get(str(v), 0) + 1
    return [FilterOption(value=v, count=c) for v, c in counts.items()]


def _range(values: list) -> Range:
    return Range(min=min(values), max=max(values)) if values else Range(min=None, max=None)


async def get_filter_options(db: AsyncSession, status: PlayerStatus | None = None) -> PlayerFilterOptions:
    query = select(Player)
    if status is not None:
        query = query.where(Player.status == status)
    players = list(await db.scalars(query))

    def ordered(options: list[FilterOption], order: list) -> list[FilterOption]:
        rank = {str(v): i for i, v in enumerate(order)}
        return sorted(options, key=lambda o: rank.get(o.value, len(order)))

    def by_name(options: list[FilterOption]) -> list[FilterOption]:
        return sorted(options, key=lambda o: o.value)

    group_of = {p: g for g, positions in POSITION_GROUPS.items() for p in positions}
    return PlayerFilterOptions(
        total=len(players),
        line_up=ordered(_options(p.line_up for p in players), LINE_UP_PRIORITY),
        position=ordered(_options(p.position for p in players), POSITION_PRIORITY),
        group=ordered(_options(group_of.get(p.position) for p in players), list(PositionGroup)),
        rank=ordered(_options(_rank_of(p.power) for p in players), list(PlayerRank)),
        club=by_name(_options(p.club for p in players)),
        league=by_name(_options(p.league for p in players)),
        nation=by_name(_options(p.nation for p in players)),
        power=_range([p.power for p in players]),
        price=_range([p.price for p in players]),
        salary=_range([p.salary for p in players]),
        age=_range([p.age for p in players]),
        sort=list(PlayerSort),
    )


async def get_player(db: AsyncSession, player_id: int) -> Player | None:
    return await db.get(Player, player_id)


async def get_squad_numbers(db: AsyncSession) -> set[int]:
    result = await db.scalars(
        select(Player.number).where(Player.status == PlayerStatus.SQUAD, Player.number.is_not(None))
    )
    return set(result)


def resolve_training(line_up: LineUp | None, training: Training | None,
                     current: Training = Training.NONE) -> Training:
    """Какая тренировка будет у игрока, если её не указали явно.

    Воспитанник сохраняет текущую (новый — умеренную), у остальных всегда «без тренировок».
    """
    if training is not None:
        return training
    if line_up != LineUp.ACADEMY:
        return Training.NONE
    return current if current != Training.NONE else Training.MODERATE


def _training_weight() -> case:
    return case(TRAINING_WEIGHTS, value=Player.training, else_=0)


async def get_academy_weight(db: AsyncSession, exclude_id: int | None = None) -> int:
    query = select(func.coalesce(func.sum(_training_weight()), 0)).where(Player.line_up == LineUp.ACADEMY)
    if exclude_id is not None:
        query = query.where(Player.id != exclude_id)
    return await db.scalar(query)


async def check_training(db: AsyncSession, line_up: LineUp | None, training: Training,
                         player_id: int | None = None) -> str | None:
    """Причина, по которой такую тренировку поставить нельзя, или None."""
    if line_up != LineUp.ACADEMY:
        if training != Training.NONE:
            return "Тренировки доступны только воспитанникам академии"
        return None
    if training == Training.NONE:
        return "У воспитанника должна быть минимум умеренная тренировка"
    used = await get_academy_weight(db, exclude_id=player_id)
    if used + TRAINING_WEIGHTS[training] > ACADEMY_WEIGHT_LIMIT:
        return (f"Превышен лимит нагрузки академии: {used} + {TRAINING_WEIGHTS[training]} "
                f"> {ACADEMY_WEIGHT_LIMIT}")
    return None


def _reset_training(player: Player) -> None:
    player.training = Training.NONE
    player.training_progress = 0
    player.training_weeks = 0


async def get_academy(db: AsyncSession) -> AcademyRead:
    players = list(await db.scalars(
        select(Player).where(Player.line_up == LineUp.ACADEMY).order_by(Player.power.desc(), Player.id)
    ))
    return AcademyRead(
        weight_used=sum(TRAINING_WEIGHTS[p.training] for p in players),
        weight_limit=ACADEMY_WEIGHT_LIMIT,
        players=players,
    )


async def set_training(db: AsyncSession, player: Player, training: Training) -> Player:
    player.training = training
    await db.commit()
    await db.refresh(player)
    return player


async def train_academy_week(db: AsyncSession, rng: random.Random = random) -> list[TrainingResult]:
    """Одна неделя (матч) тренировок академии. Не коммитит — это делает вызывающий.

    Каждую неделю к прогрессу добавляется случайный % по уровню тренировки,
    на 3-й неделе игрок получает MAX_POWER_GAIN × прогресс/100 силы и цикл начинается заново.
    Дробная часть прироста копится в power_growth, пока не наберётся целое очко.
    Игроков без тренировок не выбираем вовсе.
    """
    players = list(await db.scalars(
        select(Player)
        .where(Player.line_up == LineUp.ACADEMY, Player.training != Training.NONE)
        .order_by(Player.id)
    ))
    results = []
    for player in players:
        week_progress = rng.randint(0, TRAINING_MAX_GAIN[player.training])
        player.training_progress = min(100, player.training_progress + week_progress)
        player.training_weeks += 1

        power_gain = 0.0
        if player.training_weeks >= TRAINING_CYCLE:
            power_gain = MAX_POWER_GAIN * player.training_progress / 100
            growth = round(player.power_growth + power_gain, 4)
            whole = int(growth)
            cap = max(player.potential, player.power)  # выше потенциала тренировки не поднимают
            old_power = player.power
            player.power = min(cap, player.power + whole)
            apply_price_growth(player, old_power)
            player.power_growth = 0 if player.power == cap else growth - whole
            player.training_progress = 0
            player.training_weeks = 0

        results.append(TrainingResult(
            player_id=player.id,
            training=player.training,
            week_progress=week_progress,
            training_progress=player.training_progress,
            training_weeks=player.training_weeks,
            power_gain=power_gain,
            power=player.power,
            price=player.price,
        ))
    return results


async def create_player(db: AsyncSession, data: PlayerCreate, rng: random.Random = random) -> Player:
    player = Player(**data.model_dump())
    if player.line_up == LineUp.ACADEMY:
        player.age = rng.randint(*ACADEMY_AGE)
        player.power = rng.randint(*ACADEMY_POWER)
        player.potential = generate_potential(player.power, rng)
    elif player.potential is None:
        player.potential = generate_potential(player.power, rng)
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def update_player(db: AsyncSession, player: Player, data: PlayerUpdate) -> Player:
    was_academy = player.line_up == LineUp.ACADEMY
    old_power = player.power
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    if "price" not in data.model_fields_set:
        apply_price_growth(player, old_power)  # цену, заданную вручную, не трогаем
    player.potential = max(player.potential, player.power)  # сила выросла выше потенциала — тянем его следом
    if player.line_up != LineUp.ACADEMY:
        if was_academy:
            _leave_academy(player)
        else:
            _reset_training(player)  # тренировки только у воспитанников
    await db.commit()
    await db.refresh(player)
    return player


async def delete_player(db: AsyncSession, player: Player) -> None:
    await db.delete(player)
    await db.commit()


async def promote_player(db: AsyncSession, player: Player) -> Player:
    was_academy = player.line_up == LineUp.ACADEMY
    if player.line_up in LINE_UP_ORDER:
        next_index = (LINE_UP_ORDER.index(player.line_up) + 1) % len(LINE_UP_ORDER)
        player.line_up = LINE_UP_ORDER[next_index]
    else:
        # воспитанник (или без статуса) переводится в основную команду с самого низа
        player.line_up = LINE_UP_ORDER[0]
        if was_academy:
            _leave_academy(player)  # тренировки и прогресс сгорают, обратно в академию нельзя
        else:
            _reset_training(player)
    await db.commit()
    await db.refresh(player)
    return player


async def buy_player(db: AsyncSession, player: Player) -> Player:
    used_numbers = await get_squad_numbers(db)
    number = 1
    while number in used_numbers:
        number += 1

    player.status = PlayerStatus.SQUAD
    player.number = number
    player.line_up = LineUp.DEPTH
    await finance_service.apply_purchase(db, player.price)
    await objective_service.on_player_bought(db, player)
    await db.commit()
    await db.refresh(player)
    return player


async def sell_player(db: AsyncSession, player: Player) -> PlayerSale:
    bonus = await finance_service.apply_sale(db, player.price)
    sale = PlayerSale(player_id=player.id, price=player.price, transfer_bonus=bonus)
    await db.delete(player)
    await db.commit()
    return sale


async def reset_players(db: AsyncSession) -> list[Player]:
    await db.execute(delete(Player))
    await db.execute(insert(Player), [{**p, "potential": generate_potential(p["power"])} for p in PLAYERS])
    await db.commit()
    result = await db.scalars(select(Player).order_by(Player.id))
    return list(result)
