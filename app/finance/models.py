from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClubFinance(Base):
    """Финансы клуба — одна строка на всю игру (все суммы в млн)."""

    __tablename__ = "club_finance"

    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[int] = mapped_column(default=1)
    annual_budget: Mapped[float] = mapped_column(default=600)
    # spent — потрачено на покупки и улучшения стадиона
    spent: Mapped[float] = mapped_column(default=0)
    transfer_budget: Mapped[float] = mapped_column(default=200)
    transfer_budget_left: Mapped[float] = mapped_column(default=200)
    salary_fund: Mapped[float] = mapped_column(default=350)
    fans: Mapped[float] = mapped_column(default=500)
    fans_growth: Mapped[float] = mapped_column(default=0)
    reputation: Mapped[int] = mapped_column(default=92)
