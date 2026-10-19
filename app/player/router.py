from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.finance import service as finance_service
from app.player import service
from app.player.models import Player, PlayerStatus
from app.player.schemas import (
    AcademyRead,
    PlayerCreate,
    PlayerFilter,
    PlayerFilterOptions,
    PlayerRead,
    PlayerSale,
    PlayerUpdate,
    TrainingUpdate,
)

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


@router.get("/academy", response_model=AcademyRead)
async def read_academy(db: AsyncSession = Depends(get_db)):
    """Воспитанники и занятая нагрузка академии (лимит — сумма весов 8)."""
    return await service.get_academy(db)


@router.get("/{player_id}", response_model=PlayerRead)
async def read_player(player: Player = Depends(get_player_or_404)):
    return player


@router.post("", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
async def create_player(data: PlayerCreate, db: AsyncSession = Depends(get_db)):
    if data.status == PlayerStatus.SQUAD and data.number in await service.get_squad_numbers(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Number is already taken")
    data.training = service.resolve_training(data.line_up, data.training)
    if reason := await service.check_training(db, data.line_up, data.training):
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
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
    if "potential" in data.model_fields_set and data.potential is not None \
            and data.potential < (data.power if data.power is not None else player.power):
        raise HTTPException(status.HTTP_409_CONFLICT, "Потенциал не может быть меньше силы")
    if {"line_up", "training"} & data.model_fields_set:
        line_up = data.line_up if "line_up" in data.model_fields_set else player.line_up
        if reason := service.check_academy(player, line_up):
            raise HTTPException(status.HTTP_409_CONFLICT, reason)
        data.training = service.resolve_training(line_up, data.training, player.training)
        if reason := await service.check_training(db, line_up, data.training, player.id):
            raise HTTPException(status.HTTP_409_CONFLICT, reason)
    return await service.update_player(db, player, data)


@router.patch("/{player_id}/training", response_model=PlayerRead)
async def set_training(
    data: TrainingUpdate,
    player: Player = Depends(get_player_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Сменить тренировку воспитаннику; накопленный % цикла сохраняется."""
    if reason := await service.check_training(db, player.line_up, data.training, player.id):
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    return await service.set_training(db, player, data.training)


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
