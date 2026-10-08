from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.stadium.models import StadiumUpgrade, UpgradeType
from app.stadium.schemas import (
    StadiumBonuses,
    StadiumUpgradeCreate,
    StadiumUpgradeResult,
    StadiumUpgradeUpdate,
)
from app.stadium.seed import UPGRADES


async def get_upgrades(db: AsyncSession) -> list[StadiumUpgrade]:
    result = await db.scalars(select(StadiumUpgrade).order_by(StadiumUpgrade.id))
    return list(result)


async def get_upgrade(db: AsyncSession, upgrade_id: int) -> StadiumUpgrade | None:
    return await db.get(StadiumUpgrade, upgrade_id)


async def get_upgrade_by_name(db: AsyncSession, name: str) -> StadiumUpgrade | None:
    return await db.scalar(select(StadiumUpgrade).where(StadiumUpgrade.name == name))


async def create_upgrade(db: AsyncSession, data: StadiumUpgradeCreate) -> StadiumUpgrade:
    upgrade = StadiumUpgrade(**data.model_dump())
    db.add(upgrade)
    await db.commit()
    await db.refresh(upgrade)
    return upgrade


async def update_upgrade(db: AsyncSession, upgrade: StadiumUpgrade, data: StadiumUpgradeUpdate) -> StadiumUpgrade:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(upgrade, field, value)
    await db.commit()
    await db.refresh(upgrade)
    return upgrade


async def delete_upgrade(db: AsyncSession, upgrade: StadiumUpgrade) -> None:
    await db.delete(upgrade)
    await db.commit()


async def level_up(db: AsyncSession, upgrade: StadiumUpgrade) -> StadiumUpgradeResult:
    paid = upgrade.price
    upgrade.level += 1
    upgrade.price += upgrade.price_step
    upgrade.multiplier = round(upgrade.multiplier + upgrade.multiplier_step, 2)
    await db.commit()
    await db.refresh(upgrade)
    return StadiumUpgradeResult(upgrade=upgrade, paid=paid)


def calc_bonus(upgrades: list[StadiumUpgrade], type_: UpgradeType) -> float:
    bonus = sum(u.multiplier - 1 for u in upgrades if u.type == type_)
    return round(1 + bonus, 2)


async def get_bonuses(db: AsyncSession) -> StadiumBonuses:
    upgrades = await get_upgrades(db)
    return StadiumBonuses(
        income=calc_bonus(upgrades, UpgradeType.INCOME),
        fans=calc_bonus(upgrades, UpgradeType.FANS),
    )


async def reset_upgrades(db: AsyncSession) -> list[StadiumUpgrade]:
    await db.execute(delete(StadiumUpgrade))
    await db.execute(insert(StadiumUpgrade), UPGRADES)
    await db.commit()
    return await get_upgrades(db)
