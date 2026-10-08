from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.finance import service as finance_service
from app.stadium import service
from app.stadium.models import StadiumUpgrade
from app.stadium.schemas import (
    StadiumBonuses,
    StadiumUpgradeCreate,
    StadiumUpgradeRead,
    StadiumUpgradeResult,
    StadiumUpgradeUpdate,
)

router = APIRouter(prefix="/stadium", tags=["stadium"])


async def get_upgrade_or_404(upgrade_id: int, db: AsyncSession = Depends(get_db)) -> StadiumUpgrade:
    upgrade = await service.get_upgrade(db, upgrade_id)
    if upgrade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stadium upgrade not found")
    return upgrade


@router.get("/upgrades", response_model=list[StadiumUpgradeRead])
async def list_upgrades(db: AsyncSession = Depends(get_db)):
    return await service.get_upgrades(db)


@router.get("/bonuses", response_model=StadiumBonuses)
async def read_bonuses(db: AsyncSession = Depends(get_db)):
    return await service.get_bonuses(db)


@router.get("/upgrades/{upgrade_id}", response_model=StadiumUpgradeRead)
async def read_upgrade(upgrade: StadiumUpgrade = Depends(get_upgrade_or_404)):
    return upgrade


@router.post("/upgrades", response_model=StadiumUpgradeRead, status_code=status.HTTP_201_CREATED)
async def create_upgrade(data: StadiumUpgradeCreate, db: AsyncSession = Depends(get_db)):
    if await service.get_upgrade_by_name(db, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Upgrade with this name already exists")
    return await service.create_upgrade(db, data)


@router.patch("/upgrades/{upgrade_id}", response_model=StadiumUpgradeRead)
async def update_upgrade(
    data: StadiumUpgradeUpdate,
    upgrade: StadiumUpgrade = Depends(get_upgrade_or_404),
    db: AsyncSession = Depends(get_db),
):
    if data.name and data.name != upgrade.name and await service.get_upgrade_by_name(db, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Upgrade with this name already exists")
    return await service.update_upgrade(db, upgrade, data)


@router.delete("/upgrades/{upgrade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upgrade(upgrade: StadiumUpgrade = Depends(get_upgrade_or_404), db: AsyncSession = Depends(get_db)):
    await service.delete_upgrade(db, upgrade)


@router.post("/upgrades/{upgrade_id}/level-up", response_model=StadiumUpgradeResult)
async def level_up(upgrade: StadiumUpgrade = Depends(get_upgrade_or_404), db: AsyncSession = Depends(get_db)):
    if upgrade.level >= upgrade.max_level:
        raise HTTPException(status.HTTP_409_CONFLICT, "Upgrade is already at max level")
    if reason := await finance_service.check_can_spend(db, upgrade.price):
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    # списание пишем в ту же транзакцию, level_up её закоммитит
    await finance_service.apply_spending(db, upgrade.price)
    return await service.level_up(db, upgrade)


@router.post("/reset", response_model=list[StadiumUpgradeRead])
async def reset_upgrades(db: AsyncSession = Depends(get_db)):
    return await service.reset_upgrades(db)
