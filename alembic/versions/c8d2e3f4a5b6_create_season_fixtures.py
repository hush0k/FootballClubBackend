"""create season fixtures

Revision ID: c8d2e3f4a5b6
Revises: b7c1d2e3f4a5
Create Date: 2026-10-08 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # дефолтное расписание первого сезона создаётся в коде при первом обращении
    op.create_table('season_fixtures',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('home_team_id', sa.Integer(), nullable=True),
    sa.Column('guest_team_id', sa.Integer(), nullable=True),
    sa.Column('home_goals', sa.Integer(), nullable=True),
    sa.Column('guest_goals', sa.Integer(), nullable=True),
    sa.Column('played', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['home_team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['guest_team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_season_fixtures_round'), 'season_fixtures', ['round'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_season_fixtures_round'), table_name='season_fixtures')
    op.drop_table('season_fixtures')
