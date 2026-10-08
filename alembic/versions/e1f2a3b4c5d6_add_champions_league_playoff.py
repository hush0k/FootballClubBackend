"""add champions league playoff

Revision ID: e1f2a3b4c5d6
Revises: d9e4f5a6b7c8
Create Date: 2026-10-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd9e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

stage = sa.Enum('league', 'round_of_16', 'quarter_final', 'semi_final', 'final',
                name='stage', native_enum=False, length=32)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('season_fixtures', sa.Column('stage', stage, server_default='league', nullable=False))
    op.add_column('season_fixtures', sa.Column('home_penalties', sa.Integer(), nullable=True))
    op.add_column('season_fixtures', sa.Column('guest_penalties', sa.Integer(), nullable=True))
    # старое расписание ЛЧ (каждый с каждым) удаляем — если сезон ещё не начат,
    # ensure_schedule пересоздаст расписание в новом формате (5 туров + плей-офф)
    op.execute("""
        DELETE FROM season_fixtures WHERE NOT EXISTS (SELECT 1 FROM season_fixtures WHERE played)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM season_fixtures WHERE stage <> 'league'")
    op.drop_column('season_fixtures', 'guest_penalties')
    op.drop_column('season_fixtures', 'home_penalties')
    op.drop_column('season_fixtures', 'stage')
