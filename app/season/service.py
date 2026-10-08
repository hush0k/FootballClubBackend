import random
from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance import service as finance_service
from app.game_engine import engine
from app.game_engine import service as game_engine_service
from app.game_engine.schemas import Side
from app.objective import service as objective_service
from app.season import schedule
from app.season.models import Competition, SeasonFixture, SeasonTask, Stage, Standing, standing_sort_key
from app.season.schemas import (
    CompetitionRoundResult,
    FixtureResult,
    NextMatch,
    PenaltyScore,
    PlayoffBracket,
    RoundResult,
    ScheduledMatch,
    ScheduleRound,
    SeasonTaskCreate,
    SeasonTaskUpdate,
    StandingRead,
)
from app.team.models import Team
from app.team.schemas import TeamRead

OWN_CLUB = "Real Madrid"
CHAMPIONS_LEAGUE_SPOTS = schedule.CHAMPIONS_LEAGUE_SPANISH_SPOTS


# --- турнирная таблица ---


_sort_key = standing_sort_key


async def _participants(db: AsyncSession, competition: Competition) -> set[int | None]:
    if competition == Competition.LALIGA:
        return set(await schedule.get_laliga_participants(db))
    # в ЛЧ — те, кому поставлены матчи ЛЧ в расписании текущего сезона
    await schedule.ensure_schedule(db)
    return await schedule.get_fixture_participants(db, competition)


async def sync_standings(db: AsyncSession, competition: Competition = Competition.LALIGA) -> None:
    # добавляем строки для участников турнира, которых ещё нет в его таблице
    existing = set(await db.scalars(select(Standing.team_id).where(Standing.competition == competition)))
    missing = await _participants(db, competition) - existing
    if None in missing:
        db.add(Standing(competition=competition, team_id=None, name=OWN_CLUB))
    for team in await db.scalars(select(Team).where(Team.id.in_([i for i in missing if i is not None]))):
        db.add(Standing(competition=competition, team_id=team.id, name=team.name))
    await db.flush()


async def get_sorted_standings(db: AsyncSession, competition: Competition = Competition.LALIGA) -> list[Standing]:
    return sorted(await db.scalars(select(Standing).where(Standing.competition == competition)), key=_sort_key)


def to_table(standings: list[Standing]) -> list[StandingRead]:
    return [
        StandingRead.model_validate(s).model_copy(update={"position": i})
        for i, s in enumerate(standings, start=1)
    ]


async def get_standings(db: AsyncSession, competition: Competition = Competition.LALIGA) -> list[StandingRead]:
    await sync_standings(db, competition)
    await db.commit()
    return to_table(await get_sorted_standings(db, competition))


def record_result(standing: Standing, goals_for: int, goals_against: int, points: int) -> None:
    standing.played += 1
    standing.goals_for += goals_for
    standing.goals_against += goals_against
    standing.points += points
    if points == engine.WIN_POINTS:
        standing.wins += 1
    elif points == engine.DRAW_POINTS:
        standing.draws += 1
    else:
        standing.losses += 1


# --- расписание ---


async def _team_names(db: AsyncSession) -> dict[int | None, str]:
    names = {t.id: t.name for t in await db.scalars(select(Team))}
    names[None] = OWN_CLUB
    return names


fixture_winner = schedule.fixture_winner


def _scheduled_match(fixture: SeasonFixture, names: dict[int | None, str]) -> ScheduledMatch:
    winner = None
    if fixture.played and fixture.stage != Stage.LEAGUE:
        winner = names[fixture_winner(fixture)]
    return ScheduledMatch(
        home_team_id=fixture.home_team_id, guest_team_id=fixture.guest_team_id,
        home=names[fixture.home_team_id], guest=names[fixture.guest_team_id],
        home_goals=fixture.home_goals, guest_goals=fixture.guest_goals,
        home_penalties=fixture.home_penalties, guest_penalties=fixture.guest_penalties,
        played=fixture.played, winner=winner,
    )


def _group_rounds(
    competition: Competition, fixtures: list[SeasonFixture], names: dict[int | None, str],
) -> list[ScheduleRound]:
    rounds: dict[int, ScheduleRound] = {}
    for f in fixtures:
        rounds.setdefault(f.round, ScheduleRound(
            competition=competition, stage=f.stage, round=f.round, week=f.week, matches=[],
        ))
        rounds[f.round].matches.append(_scheduled_match(f, names))
    return list(rounds.values())


async def get_schedule(db: AsyncSession, competition: Competition = Competition.LALIGA) -> list[ScheduleRound]:
    await schedule.ensure_schedule(db)
    await db.commit()
    fixtures = await schedule.get_competition_fixtures(db, competition)
    return _group_rounds(competition, fixtures, await _team_names(db))


async def get_playoff(db: AsyncSession) -> PlayoffBracket:
    """Сетка плей-офф ЛЧ: сыгранные и назначенные раунды. Следующий раунд появляется после предыдущего."""
    await schedule.ensure_schedule(db)
    await db.commit()
    fixtures = await schedule.get_competition_fixtures(db, Competition.CHAMPIONS_LEAGUE)
    participants = await schedule.get_fixture_participants(db, Competition.CHAMPIONS_LEAGUE)
    names = await _team_names(db)
    playoff = [f for f in fixtures if f.stage != Stage.LEAGUE]
    final = [f for f in playoff if f.stage == Stage.FINAL and f.played]
    return PlayoffBracket(
        qualified=schedule.playoff_size(len(participants)),
        rounds=_group_rounds(Competition.CHAMPIONS_LEAGUE, playoff, names),
        champion=names[fixture_winner(final[0])] if final else None,
    )


async def _advance_champions_league(db: AsyncSession) -> None:
    """Когда доиграна стадия ЛЧ, создаёт следующий раунд плей-офф.

    После общего этапа — посев по таблице (1-й с последним прошедшим), дальше — победители соседних пар.
    """
    fixtures = await schedule.get_competition_fixtures(db, Competition.CHAMPIONS_LEAGUE)
    if not fixtures or not all(f.played for f in fixtures):
        return
    last_round = max(f.round for f in fixtures)
    last = [f for f in fixtures if f.round == last_round]
    if last[0].stage == Stage.FINAL:
        return
    if last[0].stage == Stage.LEAGUE:
        ranked = [s.team_id for s in await get_sorted_standings(db, Competition.CHAMPIONS_LEAGUE)]
        pairs = schedule.seed_playoff(ranked[:schedule.playoff_size(len(ranked))])
    else:
        pairs = schedule.next_playoff_pairs([fixture_winner(f) for f in last])
    teams_left = len(pairs) * 2
    week = schedule.next_playoff_week(
        max(f.week for f in fixtures), await schedule.get_season_weeks(db), teams_left.bit_length() - 1,
    )
    await schedule.add_playoff_round(db, pairs, schedule.PLAYOFF_STAGES[teams_left], last_round + 1, week)


def _is_own(fixture: SeasonFixture) -> bool:
    return fixture.home_team_id is None or fixture.guest_team_id is None


async def get_next_match(db: AsyncSession, competition: Competition | None = None) -> NextMatch | None:
    """Наш ближайший матч по расписанию (в любом турнире или в заданном), None — матчей больше нет."""
    await schedule.ensure_schedule(db)
    await db.commit()
    query = select(SeasonFixture).where(
        SeasonFixture.played.is_(False),
        (SeasonFixture.home_team_id.is_(None)) | (SeasonFixture.guest_team_id.is_(None)),
    )
    if competition is not None:
        query = query.where(SeasonFixture.competition == competition)
    # в неделе с двумя матчами первым идёт матч Ла Лиги
    own = await db.scalar(query.order_by(SeasonFixture.week, SeasonFixture.competition.desc()).limit(1))
    if own is None:
        return None
    home = own.home_team_id is None
    enemy = await db.get(Team, own.guest_team_id if home else own.home_team_id)
    return NextMatch(
        competition=own.competition, stage=own.stage, round=own.round, week=own.week,
        enemy=TeamRead.model_validate(enemy), side=Side.HOME if home else Side.GUEST,
    )


def _penalties(fixture: SeasonFixture, home_power: float, guest_power: float, rng: random.Random) -> None:
    # в плей-офф ничьей не бывает: при равном счёте — серия пенальти
    if fixture.stage != Stage.LEAGUE and fixture.home_goals == fixture.guest_goals:
        fixture.home_penalties, fixture.guest_penalties = engine.penalty_shootout(home_power, guest_power, rng)


async def play_round(
    db: AsyncSession,
    power: float,
    match_date: date | None = None,
    rng: random.Random = random,
) -> RoundResult | None:
    """Играет текущую неделю целиком: тур Ла Лиги и тур ЛЧ, если он на неё выпал.

    Клуб, играющий в обоих турнирах, проводит два матча; очки каждого идут
    в таблицу своего турнира. Матчи плей-офф ЛЧ очков не дают — проигравший
    вылетает. None — сезон доигран.
    """
    await schedule.ensure_schedule(db)
    week = await schedule.get_current_week(db)
    if week is None:
        return None
    teams = {t.id: t for t in await db.scalars(select(Team))}

    by_competition: dict[Competition, list[SeasonFixture]] = {}
    for fixture in await schedule.get_week_fixtures(db, week):
        by_competition.setdefault(fixture.competition, []).append(fixture)

    results = []
    outcomes = []
    for competition in Competition:  # сначала Ла Лига, потом ЛЧ
        fixtures = by_competition.get(competition)
        if not fixtures:
            continue
        await sync_standings(db, competition)
        rows = {s.team_id: s for s in await db.scalars(select(Standing).where(Standing.competition == competition))}
        league = fixtures[0].stage == Stage.LEAGUE

        match = None
        penalties = None
        other_matches = []
        for fixture in fixtures:
            if _is_own(fixture):
                # наш матч: результат с точки зрения Реала, переводим в хозяин/гость
                side = Side.HOME if fixture.home_team_id is None else Side.GUEST
                enemy = teams[fixture.guest_team_id if side == Side.HOME else fixture.home_team_id]
                match = game_engine_service.simulate_match(power, enemy, side, match_date, rng)
                if league:
                    own_points, enemy_points = engine.get_points(match.result)
                    record_result(rows[None], match.real_goals, match.enemy_goals, own_points)
                    record_result(rows[enemy.id], match.enemy_goals, match.real_goals, enemy_points)
                if side == Side.HOME:
                    fixture.home_goals, fixture.guest_goals = match.real_goals, match.enemy_goals
                    _penalties(fixture, power, enemy.power, rng)
                    if fixture.home_penalties is not None:
                        penalties = PenaltyScore(real=fixture.home_penalties, enemy=fixture.guest_penalties)
                else:
                    fixture.home_goals, fixture.guest_goals = match.enemy_goals, match.real_goals
                    _penalties(fixture, enemy.power, power, rng)
                    if fixture.home_penalties is not None:
                        penalties = PenaltyScore(real=fixture.guest_penalties, enemy=fixture.home_penalties)
                outcomes.append((competition, match.result))
            else:
                home, guest = teams[fixture.home_team_id], teams[fixture.guest_team_id]
                score = engine.simulate_score(home.power, guest.power, rng)
                if league:
                    home_points, guest_points = engine.get_points(score.result)
                    record_result(rows[home.id], score.real_goals, score.enemy_goals, home_points)
                    record_result(rows[guest.id], score.enemy_goals, score.real_goals, guest_points)
                fixture.home_goals, fixture.guest_goals = score.real_goals, score.enemy_goals
                _penalties(fixture, home.power, guest.power, rng)
                other_matches.append(FixtureResult(
                    home=home.name, guest=guest.name, home_goals=score.real_goals, guest_goals=score.enemy_goals,
                    home_penalties=fixture.home_penalties, guest_penalties=fixture.guest_penalties,
                ))
            fixture.played = True

        if competition == Competition.CHAMPIONS_LEAGUE:
            await db.flush()
            await _advance_champions_league(db)

        results.append(CompetitionRoundResult(
            competition=competition, stage=fixtures[0].stage, round=fixtures[0].round,
            match=match, penalties=penalties, other_matches=other_matches,
            standings=to_table(await get_sorted_standings(db, competition)),
        ))

    # болельщики и награды за все наши матчи недели, неделя сдвигается один раз
    await finance_service.apply_week_results(db, outcomes)
    await db.commit()
    return RoundResult(week=week, results=results)


async def reset_standings(db: AsyncSession, rng: random.Random = random) -> list[StandingRead]:
    # новый сезон: обнуляем Ла Лигу, флаг ЛЧ остаётся до следующего finish
    await db.execute(update(Standing).where(Standing.competition == Competition.LALIGA).values(
        played=0, wins=0, draws=0, losses=0, goals_for=0, goals_against=0, points=0,
    ))
    # состав ЛЧ меняется каждый сезон — её таблицу собираем заново
    await db.execute(delete(Standing).where(Standing.competition == Competition.CHAMPIONS_LEAGUE))
    await sync_standings(db, Competition.LALIGA)
    # новое случайное расписание обоих турниров: кто с кем и в какую неделю
    await schedule.generate_schedule(db, rng)
    # номер сезона +1, игроки стареют на год, новые цели клуба
    await objective_service.start_new_season(db, rng)
    await sync_standings(db, Competition.CHAMPIONS_LEAGUE)
    await db.commit()
    return to_table(await get_sorted_standings(db))


async def finish_season(db: AsyncSession) -> list[StandingRead]:
    """Топ-3 Ла Лиги получают флаг champions_league, остальные его теряют.

    Один раз за сезон: награды и штрафы за цели клуба, бонус за титул Ла Лиги
    и за победу в ЛЧ. Повторный вызов только возвращает таблицу.
    """
    await sync_standings(db)
    standings = await get_sorted_standings(db)
    state = await objective_service.get_state(db)
    if state.finished:
        await db.commit()
        return to_table(standings)

    for i, s in enumerate(standings):
        s.champions_league = i < CHAMPIONS_LEAGUE_SPOTS
    await objective_service.evaluate_season(db)
    if standings and standings[0].team_id is None:
        await finance_service.apply_budget_change(db, finance_service.LALIGA_TITLE_BONUS)
    final = await db.scalar(select(SeasonFixture).where(
        SeasonFixture.competition == Competition.CHAMPIONS_LEAGUE,
        SeasonFixture.stage == Stage.FINAL,
        SeasonFixture.played,
    ))
    if final is not None and fixture_winner(final) is None:
        await finance_service.apply_budget_change(db, finance_service.CHAMPIONS_LEAGUE_TITLE_BONUS)
    state.finished = True
    await db.commit()
    return to_table(standings)


async def get_champions_league_teams(db: AsyncSession) -> list[Standing]:
    """Клубы Ла Лиги, квалифицировавшиеся в ЛЧ по итогам прошлого сезона."""
    result = await db.scalars(
        select(Standing).where(Standing.competition == Competition.LALIGA, Standing.champions_league)
    )
    return sorted(result, key=_sort_key)


# --- задачи на сезон ---


async def get_tasks(db: AsyncSession) -> list[SeasonTask]:
    result = await db.scalars(select(SeasonTask).order_by(SeasonTask.id))
    return list(result)


async def get_task(db: AsyncSession, task_id: int) -> SeasonTask | None:
    return await db.get(SeasonTask, task_id)


async def create_task(db: AsyncSession, data: SeasonTaskCreate) -> SeasonTask:
    task = SeasonTask(**data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(db: AsyncSession, task: SeasonTask, data: SeasonTaskUpdate) -> SeasonTask:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task: SeasonTask) -> None:
    await db.delete(task)
    await db.commit()
