"""create club finance

Revision ID: b7c1d2e3f4a5
Revises: ea3b8fa3a931
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = 'ea3b8fa3a931'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('club_finance',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('week', sa.Integer(), nullable=False),
    sa.Column('annual_budget', sa.Double(), nullable=False),
    sa.Column('spent', sa.Double(), nullable=False),
    sa.Column('transfer_budget', sa.Double(), nullable=False),
    sa.Column('transfer_budget_left', sa.Double(), nullable=False),
    sa.Column('salary_fund', sa.Double(), nullable=False),
    sa.Column('fans', sa.Double(), nullable=False),
    sa.Column('fans_growth', sa.Double(), nullable=False),
    sa.Column('reputation', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    finance = sa.table(
        'club_finance',
        sa.column('week', sa.Integer), sa.column('annual_budget', sa.Double), sa.column('spent', sa.Double),
        sa.column('transfer_budget', sa.Double), sa.column('transfer_budget_left', sa.Double),
        sa.column('salary_fund', sa.Double), sa.column('fans', sa.Double), sa.column('fans_growth', sa.Double),
        sa.column('reputation', sa.Integer),
    )
    op.bulk_insert(finance, [{
        "week": 1, "annual_budget": 600, "spent": 0, "transfer_budget": 200, "transfer_budget_left": 200,
        "salary_fund": 350, "fans": 500, "fans_growth": 0, "reputation": 92,
    }])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('club_finance')
