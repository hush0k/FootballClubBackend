from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.finance import service as finance_service
from app.player import service
from app.player.models import Player, PlayerStatus
from app.player.schemas import PlayerCreate, PlayerFilter, PlayerFilterOptions, PlayerRead, PlayerSale, PlayerUpdate

router = APIRouter(prefix="/player", tags=["player"])


async def get_player_or_404(player_id: int, db: AsyncSession = Depends(get_db)) -> Player:
    player = await service.get_player(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    return player


def ensure_status(player: Player, expected: PlayerStatus) -> None:
    if player.status != expected:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Player is not in {expected.value}")


@router.get("", response_model=list[PlayerRead])
async def list_players(
    response: Response,
    filters: Annotated[PlayerFilter, Query()],
    db: AsyncSession = Depends(get_db),
):
    """Состав (status=squad) или маркет (status=market) с фильтрами и сортировкой.

    Общее число найденных без limit/offset — в заголовке X-Total-Count («Показано X из Y»).
    """
    players, total = await service.get_players(db, filters)
    response.headers["X-Total-Count"] = str(total)
    return players


@router.post("/reset", response_model=list[PlayerRead])
async def reset_players(db: AsyncSession = Depends(get_db)):
    return await service.reset_players(db)


@router.get("/filters", response_model=PlayerFilterOptions)
async def filter_options(status_: Annotated[PlayerStatus | None, Query(alias="status")] = None,
                         db: AsyncSession = Depends(get_db)):
    """Значения для выпадающих списков фильтров и сколько игроков под каждым."""
    return await service.get_filter_options(db, status_)


@router.get("/{player_id}", response_model=PlayerRead)
async def read_player(player: Player = Depends(get_player_or_404)):
    return player


@router.post("", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
async def create_player(data: PlayerCreate, db: AsyncSession = Depends(get_db)):
    if data.status == PlayerStatus.SQUAD and data.number in await service.get_squad_numbers(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Number is already taken")
    return await service.create_player(db, data)


@router.patch("/{player_id}", response_model=PlayerRead)
async def update_player(
    data: PlayerUpdate,
    player: Player = Depends(get_player_or_404),
    db: AsyncSession = Depends(get_db),
):
    if (
        player.status == PlayerStatus.SQUAD
        and data.number is not None
        and data.number != player.number
        and data.number in await service.get_squad_numbers(db)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Number is already taken")
    return await service.update_player(db, player, data)


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(player: Player = Depends(get_player_or_404), db: AsyncSession = Depends(get_db)):
    await service.delete_player(db, player)


@router.post("/{player_id}/promote", response_model=PlayerRead)
async def promote_player(player: Player = Depends(get_player_or_404), db: AsyncSession = Depends(get_db)):
    ensure_status(player, PlayerStatus.SQUAD)
    return await service.promote_player(db, player)


@router.post("/{player_id}/buy", response_model=PlayerRead)
async def buy_player(player: Player = Depends(get_player_or_404), db: AsyncSession = Depends(get_db)):
    ensure_status(player, PlayerStatus.MARKET)
    if reason := await finance_service.check_can_buy(db, player):
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    return await service.buy_player(db, player)


@router.post("/{player_id}/sell", response_model=PlayerSale)
async def sell_player(player: Player = Depends(get_player_or_404), db: AsyncSession = Depends(get_db)):
    ensure_status(player, PlayerStatus.SQUAD)
    return await service.sell_player(db, player)
