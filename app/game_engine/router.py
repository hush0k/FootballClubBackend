from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.game_engine import service
from app.game_engine.schemas import MatchRequest, MatchResult, TeamPower, WinChance
from app.team import service as team_service
from app.team.models import Team

router = APIRouter(prefix="/game-engine", tags=["game_engine"])


async def get_power_or_409(db: AsyncSession = Depends(get_db)) -> TeamPower:
    power = await service.get_team_power(db)
    if power is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No players in the starting line-up")
    return power


async def get_enemy_or_404(enemy_id: int, db: AsyncSession = Depends(get_db)) -> Team:
    team = await team_service.get_team(db, enemy_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return team


@router.get("/team-power", response_model=TeamPower)
async def read_team_power(power: TeamPower = Depends(get_power_or_409)):
    return power


@router.get("/win-chance/{enemy_id}", response_model=WinChance)
async def read_win_chance(
    enemy: Team = Depends(get_enemy_or_404),
    power: TeamPower = Depends(get_power_or_409),
):
    return service.get_win_chance(power.power, enemy)


@router.post("/simulate", response_model=MatchResult)
async def simulate_match(
    data: MatchRequest,
    power: TeamPower = Depends(get_power_or_409),
    db: AsyncSession = Depends(get_db),
):
    enemy = await get_enemy_or_404(data.enemy_id, db)
    return service.simulate_match(power.power, enemy, data.side, data.date)


@router.get("/last-five", response_model=list[MatchResult])
async def last_five_matches(power: TeamPower = Depends(get_power_or_409), db: AsyncSession = Depends(get_db)):
    return await service.last_five_matches(db, power.power)
