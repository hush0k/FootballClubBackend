"""add academy training

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # line_up хранится строкой без CHECK, поэтому «Воспитанник» отдельной миграции не требует
    op.add_column('players', sa.Column(
        'training',
        sa.Enum('Без тренировок', 'Умеренная тренировка', 'Обычная тренировка', 'Интенсивная тренировка',
                name='training', native_enum=False, length=32),
        nullable=False, server_default='Без тренировок',
    ))
    op.add_column('players', sa.Column('training_progress', sa.Integer(), nullable=False, server_default=sa.text('0')))
    op.add_column('players', sa.Column('training_weeks', sa.Integer(), nullable=False, server_default=sa.text('0')))
    op.add_column('players', sa.Column('power_growth', sa.Float(), nullable=False, server_default=sa.text('0')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('players', 'power_growth')
    op.drop_column('players', 'training_weeks')
    op.drop_column('players', 'training_progress')
    op.drop_column('players', 'training')
