from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.objective import service
from app.objective.schemas import ObjectiveRead, SeasonObjectives, SquadAge

router = APIRouter(prefix="/objectives", tags=["objectives"])


@router.get("", response_model=SeasonObjectives)
async def get_objectives(db: AsyncSession = Depends(get_db)):
    """Цели текущего сезона с прогрессом: условие, награда, штраф, уровень и target."""
    state, objectives = await service.get_current(db)
    return SeasonObjectives(season=state.season, finished=state.finished, objectives=objectives)


@router.get("/history", response_model=list[ObjectiveRead])
async def get_history(db: AsyncSession = Depends(get_db)):
    """Цели всех сезонов, включая выполненные и проваленные."""
    return await service.get_all_objectives(db)


@router.get("/squad-age", response_model=SquadAge)
async def get_squad_age(db: AsyncSession = Depends(get_db)):
    """Средний возраст основного состава и нужно ли его омолодить (больше 30 лет)."""
    return await service.get_squad_age(db)


@router.post("/reset", response_model=SeasonObjectives)
async def reset_objectives(db: AsyncSession = Depends(get_db)):
    """Сбрасывает цели и уровни — начинается 1-й сезон. Возраст игроков не откатывается."""
    state, objectives = await service.reset(db)
    return SeasonObjectives(season=state.season, finished=state.finished, objectives=objectives)
