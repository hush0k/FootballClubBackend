"""add player potential and left_academy

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-10-19 14:00:00.000000

"""
import random
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _potential(power: int) -> int:
    # копия player.service.generate_potential на момент миграции
    if power >= 99:
        return power
    for _ in range(100):
        potential = round(random.gauss(83.5, 7))
        if power <= potential <= 99:
            return potential
    return random.randint(power, 99)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('players', sa.Column('potential', sa.Integer(), nullable=True))
    op.add_column('players', sa.Column('left_academy', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # существующим игрокам потенциал выпадает так же, как новым
    conn = op.get_bind()
    players = sa.table('players', sa.column('id', sa.Integer), sa.column('power', sa.Integer),
                       sa.column('potential', sa.Integer))
    for player_id, power in conn.execute(sa.select(players.c.id, players.c.power)).all():
        conn.execute(players.update().where(players.c.id == player_id).values(potential=_potential(power)))
    op.alter_column('players', 'potential', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('players', 'left_academy')
    op.drop_column('players', 'potential')
