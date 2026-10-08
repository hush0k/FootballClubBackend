from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.team.models import Team
from app.team.schemas import TeamCreate, TeamUpdate


async def get_teams(db: AsyncSession) -> list[Team]:
    result = await db.scalars(select(Team).order_by(Team.id))
    return list(result)


async def get_team(db: AsyncSession, team_id: int) -> Team | None:
    return await db.get(Team, team_id)


async def get_team_by_name(db: AsyncSession, name: str) -> Team | None:
    return await db.scalar(select(Team).where(Team.name == name))


async def create_team(db: AsyncSession, data: TeamCreate) -> Team:
    team = Team(**data.model_dump())
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


async def update_team(db: AsyncSession, team: Team, data: TeamUpdate) -> Team:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    await db.commit()
    await db.refresh(team)
    return team


async def delete_team(db: AsyncSession, team: Team) -> None:
    await db.delete(team)
    await db.commit()
