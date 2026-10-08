from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SeasonStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    WIN = "win"  # меньше 5 поражений
    FINISHED = "finished"
    LOSE = "lose"  # больше 12 поражений


class FinanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week: int
    annual_budget: float
    spent: float
    transfer_budget: float
    transfer_budget_left: float
    salary_fund: float
    fans: float
    fans_growth: float
    reputation: int


class FinanceSummary(FinanceRead):
    """Состояние финансов + производные значения (как в App.jsx)."""

    all_salary: float
    available_budget: float
    income_bonus: float
    fans_bonus: float
    win_reward: float  # Ла Лига
    draw_reward: float
    champions_league_win_reward: float
    champions_league_draw_reward: float
    fan_penalty: float
    effective_salary_fund: float
    effective_transfer_budget: float
    effective_transfer_left: float
    matches_played: int
    season_rounds: int
    season_status: SeasonStatus
