from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.finance import service
from app.finance.schemas import FinanceSummary

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("", response_model=FinanceSummary)
async def read_finance(db: AsyncSession = Depends(get_db)):
    summary = await service.get_summary(db)
    await db.commit()  # на случай, если строка финансов была создана впервые
    return summary


@router.post("/reset", response_model=FinanceSummary)
async def reset_finance(db: AsyncSession = Depends(get_db)):
    return await service.reset_finance(db)
