"""add teams with logos and club objectives

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

objective_type = sa.Enum('laliga_place', 'champions_league', 'rejuvenate', 'star_player', 'el_clasico',
                         name='objective_type', native_enum=False, length=32)
objective_status = sa.Enum('active', 'completed', 'failed', name='objective_status', native_enum=False, length=32)

LOGO = '.football-logos.cc.svg'

# логотипы из public фронтенда для уже существующих клубов: (имя, новый файл, старый файл)
LOGO_FIXES = [
    ("Manchester City", "england_manchester-city", "manchester-city.svg"),
    ("Bayern Munich", "germany_bayern-munchen", "bayern.svg"),
    ("Liverpool", "england_liverpool", "liverpool.svg"),
    ("Inter", "italy_inter", "inter.svg"),
]

LALIGA_TEAMS = [
    ("Rayo Vallecano", "spain_rayo-vallecano", 70, "Эстадио де Вальекас"),
    ("Getafe", "spain_getafe", 69, "Колисеум Альфонсо Перес"),
    ("Elche", "spain_elche", 67, "Мартинес Валеро"),
    ("Málaga", "spain_malaga", 65, "Ла Росаледа"),
    ("Racing Santander", "spain_racing", 65, "Эль Сардинеро"),
]

FOREIGN_TEAMS = [
    ("Arsenal", "england_arsenal", 86, "Эмирейтс"),
    ("Borussia Dortmund", "germany_borussia-dortmund", 82, "Сигнал Идуна Парк"),
    ("Manchester United", "england_manchester-united", 80, "Олд Траффорд"),
    ("Aston Villa", "england_aston-villa", 80, "Вилла Парк"),
    ("RB Leipzig", "germany_rb-leipzig", 79, "Ред Булл Арена"),
    ("Roma", "italy_roma", 79, "Стадио Олимпико"),
    ("Sporting CP", "portugal_sporting-cp", 78, "Жозе Алваладе"),
    ("FC Porto", "portugal_fc-porto", 78, "Драгау"),
    ("PSV", "netherlands_psv", 77, "Филипс Стадион"),
    ("VfB Stuttgart", "germany_vfb-stuttgart", 77, "МХП Арена"),
    ("Lille", "france_lille", 76, "Пьер Моруа"),
    ("Feyenoord", "netherlands_feyenoord", 76, "Де Кейп"),
    ("Galatasaray", "turkey_galatasaray", 76, "РАМС Парк"),
    ("Fenerbahçe", "turkey_fenerbahce", 75, "Шюкрю Сараджоглу"),
    ("Club Brugge", "belgium_club-brugge", 74, "Ян Брейдел"),
    ("Shakhtar Donetsk", "ukraine_shakhtar", 73, "Донбасс Арена"),
    ("Bodø/Glimt", "norway_bodo-glimt", 72, "Аспмюра"),
    ("Slavia Praha", "czech-republic_slavia-praha", 71, "Фортуна Арена"),
    ("Slovan Bratislava", "slovakia_s-bratislava", 70, "Техелне поле"),
]


def upgrade() -> None:
    """Upgrade schema."""
    teams = sa.table(
        'teams',
        sa.column('name', sa.String), sa.column('img_url', sa.String), sa.column('power', sa.Integer),
        sa.column('stadium', sa.String), sa.column('league', sa.String),
    )
    for name, logo, _ in LOGO_FIXES:
        op.execute(teams.update().where(teams.c.name == name).values(img_url=logo + LOGO))
    op.bulk_insert(teams, [
        {"name": name, "img_url": logo + LOGO, "power": power, "stadium": stadium, "league": league}
        for league, rows in (("laliga", LALIGA_TEAMS), ("foreign", FOREIGN_TEAMS))
        for name, logo, power, stadium in rows
    ])

    op.create_table(
        'club_objectives',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('type', objective_type, nullable=False),
        sa.Column('level', sa.Integer(), nullable=True),
        sa.Column('target', sa.Integer(), nullable=False),
        sa.Column('condition', sa.String(length=255), nullable=False),
        sa.Column('reward', sa.Float(), nullable=False),
        sa.Column('penalty', sa.Float(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=False),
        sa.Column('status', objective_status, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_club_objectives_season'), 'club_objectives', ['season'], unique=False)
    op.create_table(
        'club_objective_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('finished', sa.Boolean(), nullable=False),
        sa.Column('laliga_level', sa.Integer(), nullable=False),
        sa.Column('champions_league_level', sa.Integer(), nullable=False),
        sa.Column('clasico_level', sa.Integer(), nullable=False),
        sa.Column('star_last_season', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('club_objective_state')
    op.drop_index(op.f('ix_club_objectives_season'), table_name='club_objectives')
    op.drop_table('club_objectives')

    names = [name for rows in (LALIGA_TEAMS, FOREIGN_TEAMS) for name, *_ in rows]
    op.execute(sa.text("DELETE FROM teams WHERE name = ANY(:names)").bindparams(names=names))
    teams = sa.table('teams', sa.column('name', sa.String), sa.column('img_url', sa.String))
    for name, _, old_logo in LOGO_FIXES:
        op.execute(teams.update().where(teams.c.name == name).values(img_url=old_logo))
