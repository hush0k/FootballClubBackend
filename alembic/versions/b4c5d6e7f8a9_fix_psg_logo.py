"""fix psg logo

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAME = "Paris Saint-Germain"
NEW_LOGO = "france_paris-saint-germain.football-logos.cc.svg"
OLD_LOGO = "psg.svg"

teams = sa.table('teams', sa.column('name', sa.String), sa.column('img_url', sa.String))


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(teams.update().where(teams.c.name == NAME).values(img_url=NEW_LOGO))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(teams.update().where(teams.c.name == NAME).values(img_url=OLD_LOGO))
