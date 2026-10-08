from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach.models import Coach
from app.coach.schemas import CoachCreate, CoachUpdate


async def get_coaches(db: AsyncSession) -> list[Coach]:
    result = await db.scalars(select(Coach).order_by(Coach.id))
    return list(result)


async def get_coach(db: AsyncSession, coach_id: int) -> Coach | None:
    return await db.get(Coach, coach_id)


async def get_total_salary(db: AsyncSession) -> float:
    # зарплаты штаба входят в общий фонд зарплат (allSalary во фронте) — пригодится season
    return await db.scalar(select(func.coalesce(func.sum(Coach.salary), 0.0)))


async def create_coach(db: AsyncSession, data: CoachCreate) -> Coach:
    coach = Coach(**data.model_dump())
    db.add(coach)
    await db.commit()
    await db.refresh(coach)
    return coach


async def update_coach(db: AsyncSession, coach: Coach, data: CoachUpdate) -> Coach:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(coach, field, value)
    await db.commit()
    await db.refresh(coach)
    return coach


async def delete_coach(db: AsyncSession, coach: Coach) -> None:
    await db.delete(coach)
    await db.commit()
