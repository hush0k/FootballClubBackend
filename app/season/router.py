from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.finance import service as finance_service
from app.finance.schemas import SeasonStatus
from app.game_engine.router import get_power_or_409
from app.game_engine.schemas import TeamPower
from app.season import service
from app.season.models import Competition, SeasonTask
from app.season.schemas import (
    NextMatch,
    NextWeek,
    RoundRequest,
    RoundResult,
    ScheduleRound,
    SeasonTaskCreate,
    SeasonHistoryRead,
    SeasonTaskRead,
    SeasonTaskUpdate,
    StandingRead,
)

router = APIRouter(prefix="/season", tags=["season"])

STARTERS_COUNT = 11


async def get_task_or_404(task_id: int, db: AsyncSession = Depends(get_db)) -> SeasonTask:
    task = await service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.get("/standings", response_model=list[StandingRead])
async def read_standings(db: AsyncSession = Depends(get_db)):
    return await service.get_standings(db)


@router.get("/schedule", response_model=list[ScheduleRound])
async def read_schedule(competition: Competition = Competition.LALIGA, db: AsyncSession = Depends(get_db)):
    return await service.get_schedule(db, competition)


@router.get("/next-match", response_model=NextMatch)
async def read_next_match(db: AsyncSession = Depends(get_db)):
    match = await service.get_next_match(db)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Season is over")
    return match


@router.get("/next-week", response_model=NextWeek)
async def read_next_week(db: AsyncSession = Depends(get_db)):
    week = await service.get_next_week(db)
    if week is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Season is over")
    return week


@router.post("/round", response_model=RoundResult)
async def play_round(
    data: RoundRequest,
    power: TeamPower = Depends(get_power_or_409),
    db: AsyncSession = Depends(get_db),
):
    if power.starters != STARTERS_COUNT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"В основном составе должно быть ровно {STARTERS_COUNT} игроков, сейчас {power.starters}",
        )
    if (await finance_service.get_summary(db)).season_status != SeasonStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Season is over")
    result = await service.play_round(db, power.power, data.date)
    if result is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Season is over")
    return result


@router.post("/finish", response_model=list[StandingRead])
async def finish_season(db: AsyncSession = Depends(get_db)):
    if not await service.is_season_played(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Season is not over yet")
    return await service.finish_season(db)


@router.post("/reset", response_model=list[StandingRead])
async def reset_standings(db: AsyncSession = Depends(get_db)):
    return await service.reset_standings(db)


@router.get("/history", response_model=list[SeasonHistoryRead])
async def read_history(db: AsyncSession = Depends(get_db)):
    return await service.get_history(db)


@router.get("/tasks", response_model=list[SeasonTaskRead])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    return await service.get_tasks(db)


@router.get("/tasks/{task_id}", response_model=SeasonTaskRead)
async def read_task(task: SeasonTask = Depends(get_task_or_404)):
    return task


@router.post("/tasks", response_model=SeasonTaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(data: SeasonTaskCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_task(db, data)


@router.patch("/tasks/{task_id}", response_model=SeasonTaskRead)
async def update_task(
    data: SeasonTaskUpdate,
    task: SeasonTask = Depends(get_task_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_task(db, task, data)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task: SeasonTask = Depends(get_task_or_404), db: AsyncSession = Depends(get_db)):
    await service.delete_task(db, task)
