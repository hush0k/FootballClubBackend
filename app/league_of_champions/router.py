from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.season import service as season_service
from app.season.models import Competition
from app.season.schemas import NextMatch, PlayoffBracket, ScheduleRound, StandingRead

router = APIRouter(prefix="/league-of-champions", tags=["league_of_champions"])


@router.get("/participants", response_model=list[StandingRead])
async def read_participants(db: AsyncSession = Depends(get_db)):
    # клубы Ла Лиги, прошедшие в ЛЧ — топ-3 последнего завершённого сезона (флаг ставит /season/finish)
    return season_service.to_table(await season_service.get_champions_league_teams(db))


@router.get("/standings", response_model=list[StandingRead])
async def read_standings(db: AsyncSession = Depends(get_db)):
    return await season_service.get_standings(db, Competition.CHAMPIONS_LEAGUE)


@router.get("/schedule", response_model=list[ScheduleRound])
async def read_schedule(db: AsyncSession = Depends(get_db)):
    return await season_service.get_schedule(db, Competition.CHAMPIONS_LEAGUE)


@router.get("/playoff", response_model=PlayoffBracket)
async def read_playoff(db: AsyncSession = Depends(get_db)):
    # сетка плей-офф; пары следующего раунда появляются, когда доигран предыдущий
    return await season_service.get_playoff(db)


@router.get("/next-match", response_model=NextMatch)
async def read_next_match(db: AsyncSession = Depends(get_db)):
    match = await season_service.get_next_match(db, Competition.CHAMPIONS_LEAGUE)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет предстоящих матчей ЛЧ")
    return match
