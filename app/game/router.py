from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.finance import service as finance_service
from app.finance.schemas import FinanceSummary
from app.objective import service as objective_service
from app.player import service as player_service
from app.season import service as season_service
from app.stadium import service as stadium_service

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/reset", response_model=FinanceSummary)
async def reset_game(db: AsyncSession = Depends(get_db)):
    await finance_service.reset_finance(db)
    await season_service.reset_standings(db)
    await season_service.clear_history(db)
    await objective_service.reset(db)
    await player_service.reset_players(db)
    await stadium_service.reset_upgrades(db)
    return await finance_service.get_summary(db)
