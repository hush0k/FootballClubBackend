from sqlalchemy import Select, case, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance import service as finance_service
from app.objective import service as objective_service
from app.player.models import LineUp, Player, PlayerStatus, Position
from app.player.schemas import (
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
)
from app.player.seed import PLAYERS

# порядок статусов при "Изменить статус": по кругу от глубины к основе
LINE_UP_ORDER = [LineUp.DEPTH, LineUp.BENCH, LineUp.ROTATION, LineUp.STARTER]

# сортировка состава по умолчанию, как во фронте: статус → позиция → сила
LINE_UP_PRIORITY = [LineUp.STARTER, LineUp.ROTATION, LineUp.BENCH, LineUp.DEPTH]
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


async def create_player(db: AsyncSession, data: PlayerCreate) -> Player:
    player = Player(**data.model_dump())
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def update_player(db: AsyncSession, player: Player, data: PlayerUpdate) -> Player:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    await db.commit()
    await db.refresh(player)
    return player


async def delete_player(db: AsyncSession, player: Player) -> None:
    await db.delete(player)
    await db.commit()


async def promote_player(db: AsyncSession, player: Player) -> Player:
    next_index = (LINE_UP_ORDER.index(player.line_up) + 1) % len(LINE_UP_ORDER)
    player.line_up = LINE_UP_ORDER[next_index]
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
    await db.execute(insert(Player), PLAYERS)
    await db.commit()
    result = await db.scalars(select(Player).order_by(Player.id))
    return list(result)
