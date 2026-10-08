from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach import service
from app.coach.models import Coach
from app.coach.schemas import CoachCreate, CoachRead, CoachUpdate
from app.core.database import get_db

router = APIRouter(prefix="/coach", tags=["coach"])


async def get_coach_or_404(coach_id: int, db: AsyncSession = Depends(get_db)) -> Coach:
    coach = await service.get_coach(db, coach_id)
    if coach is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coach not found")
    return coach


@router.get("", response_model=list[CoachRead])
async def list_coaches(db: AsyncSession = Depends(get_db)):
    return await service.get_coaches(db)


@router.get("/{coach_id}", response_model=CoachRead)
async def read_coach(coach: Coach = Depends(get_coach_or_404)):
    return coach


@router.post("", response_model=CoachRead, status_code=status.HTTP_201_CREATED)
async def create_coach(data: CoachCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_coach(db, data)


@router.patch("/{coach_id}", response_model=CoachRead)
async def update_coach(
    data: CoachUpdate,
    coach: Coach = Depends(get_coach_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_coach(db, coach, data)


@router.delete("/{coach_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coach(coach: Coach = Depends(get_coach_or_404), db: AsyncSession = Depends(get_db)):
    await service.delete_coach(db, coach)
