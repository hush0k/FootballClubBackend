"""create season history

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('season_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('laliga_position', sa.Integer(), nullable=False),
    sa.Column('laliga_total', sa.Integer(), nullable=False),
    sa.Column('laliga_points', sa.Integer(), nullable=False),
    sa.Column('laliga_wins', sa.Integer(), nullable=False),
    sa.Column('laliga_draws', sa.Integer(), nullable=False),
    sa.Column('laliga_losses', sa.Integer(), nullable=False),
    sa.Column('champions_league_position', sa.Integer(), nullable=True),
    sa.Column('champions_league_total', sa.Integer(), nullable=True),
    sa.Column('champions_league_points', sa.Integer(), nullable=True),
    sa.Column('champions_league_wins', sa.Integer(), nullable=True),
    sa.Column('champions_league_draws', sa.Integer(), nullable=True),
    sa.Column('champions_league_losses', sa.Integer(), nullable=True),
    sa.Column('playoff_stage', sa.String(length=32), nullable=True),
    sa.Column('champions_league_champion', sa.Boolean(), nullable=False),
    sa.Column('laliga_earnings', sa.Double(), nullable=False),
    sa.Column('champions_league_earnings', sa.Double(), nullable=False),
    sa.Column('title_bonuses', sa.Double(), nullable=False),
    sa.Column('objectives_earnings', sa.Double(), nullable=False),
    sa.Column('budget', sa.Double(), nullable=False),
    sa.Column('fans', sa.Double(), nullable=False),
    sa.Column('reputation', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_season_history_season'), 'season_history', ['season'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_season_history_season'), table_name='season_history')
    op.drop_table('season_history')
