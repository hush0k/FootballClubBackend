from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.team import service
from app.team.models import Team
from app.team.schemas import TeamCreate, TeamRead, TeamUpdate

router = APIRouter(prefix="/team", tags=["team"])


async def get_team_or_404(team_id: int, db: AsyncSession = Depends(get_db)) -> Team:
    team = await service.get_team(db, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return team


@router.get("", response_model=list[TeamRead])
async def list_teams(db: AsyncSession = Depends(get_db)):
    return await service.get_teams(db)


@router.get("/{team_id}", response_model=TeamRead)
async def read_team(team: Team = Depends(get_team_or_404)):
    return team


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(data: TeamCreate, db: AsyncSession = Depends(get_db)):
    if await service.get_team_by_name(db, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Team with this name already exists")
    return await service.create_team(db, data)


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team(
    data: TeamUpdate,
    team: Team = Depends(get_team_or_404),
    db: AsyncSession = Depends(get_db),
):
    if data.name and data.name != team.name and await service.get_team_by_name(db, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Team with this name already exists")
    return await service.update_team(db, team, data)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team: Team = Depends(get_team_or_404), db: AsyncSession = Depends(get_db)):
    await service.delete_team(db, team)
