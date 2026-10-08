"""add champions league: team league, competition in standings and fixtures

Revision ID: d9e4f5a6b7c8
Revises: c8d2e3f4a5b6
Create Date: 2026-10-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c8d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

league = sa.Enum('laliga', 'foreign', name='league', native_enum=False, length=32)
competition = sa.Enum('laliga', 'champions_league', name='competition', native_enum=False, length=32)


def upgrade() -> None:
    """Upgrade schema."""
    # --- teams: домашняя лига, существующие клубы — Ла Лига ---
    op.add_column('teams', sa.Column('league', league, nullable=False, server_default='laliga'))
    op.alter_column('teams', 'league', server_default=None)
    op.create_index(op.f('ix_teams_league'), 'teams', ['league'], unique=False)

    teams = sa.table(
        'teams',
        sa.column('name', sa.String), sa.column('img_url', sa.String), sa.column('power', sa.Integer),
        sa.column('stadium', sa.String), sa.column('league', sa.String),
    )
    # иностранные участники ЛЧ (испанцы попадают туда через топ-3 Ла Лиги)
    op.bulk_insert(teams, [
        {"name": "Manchester City", "img_url": "manchester-city.svg", "power": 89, "stadium": "Этихад", "league": "foreign"},
        {"name": "Bayern Munich", "img_url": "bayern.svg", "power": 88, "stadium": "Альянц Арена", "league": "foreign"},
        {"name": "Liverpool", "img_url": "liverpool.svg", "power": 87, "stadium": "Энфилд", "league": "foreign"},
        {"name": "Paris Saint-Germain", "img_url": "psg.svg", "power": 86, "stadium": "Парк де Пренс", "league": "foreign"},
        {"name": "Inter", "img_url": "inter.svg", "power": 84, "stadium": "Сан-Сиро", "league": "foreign"},
    ])

    # --- season_standings: отдельная таблица на каждый турнир ---
    op.add_column('season_standings', sa.Column('competition', competition, nullable=False, server_default='laliga'))
    op.alter_column('season_standings', 'competition', server_default=None)
    op.create_index(op.f('ix_season_standings_competition'), 'season_standings', ['competition'], unique=False)
    op.drop_constraint('season_standings_name_key', 'season_standings', type_='unique')
    op.drop_constraint('season_standings_team_id_key', 'season_standings', type_='unique')
    op.create_unique_constraint(
        'season_standings_competition_team_id_key', 'season_standings', ['competition', 'team_id'],
        postgresql_nulls_not_distinct=True,
    )

    # --- season_fixtures: турнир + неделя; у старых матчей Ла Лиги неделя = тур ---
    op.add_column('season_fixtures', sa.Column('competition', competition, nullable=False, server_default='laliga'))
    op.alter_column('season_fixtures', 'competition', server_default=None)
    op.add_column('season_fixtures', sa.Column('week', sa.Integer(), nullable=True))
    op.execute("UPDATE season_fixtures SET week = round")
    op.alter_column('season_fixtures', 'week', nullable=False)
    op.create_index(op.f('ix_season_fixtures_competition'), 'season_fixtures', ['competition'], unique=False)
    op.create_index(op.f('ix_season_fixtures_week'), 'season_fixtures', ['week'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_season_fixtures_week'), table_name='season_fixtures')
    op.drop_index(op.f('ix_season_fixtures_competition'), table_name='season_fixtures')
    op.execute("DELETE FROM season_fixtures WHERE competition = 'champions_league'")
    op.drop_column('season_fixtures', 'week')
    op.drop_column('season_fixtures', 'competition')

    op.execute("DELETE FROM season_standings WHERE competition = 'champions_league'")
    op.drop_constraint('season_standings_competition_team_id_key', 'season_standings', type_='unique')
    op.create_unique_constraint('season_standings_team_id_key', 'season_standings', ['team_id'])
    op.create_unique_constraint('season_standings_name_key', 'season_standings', ['name'])
    op.drop_index(op.f('ix_season_standings_competition'), table_name='season_standings')
    op.drop_column('season_standings', 'competition')

    op.execute("DELETE FROM teams WHERE league = 'foreign'")
    op.drop_index(op.f('ix_teams_league'), table_name='teams')
    op.drop_column('teams', 'league')
