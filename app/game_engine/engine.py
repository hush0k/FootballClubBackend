"""Чистая логика движка (порт matchRandomizerEngin.js), без БД.

Все функции принимают rng, чтобы результат можно было зафиксировать в тестах.
"""
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

from app.game_engine.schemas import MatchOutcome

T = TypeVar("T")

WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0


@dataclass(frozen=True)
class Chances:
    win: float
    draw: float
    lose: float


@dataclass(frozen=True)
class Score:
    real_goals: int
    enemy_goals: int
    result: MatchOutcome


def get_win_chance(power_a: float, power_b: float, spread: float = 10) -> float:
    # Эло-подобная формула: +10 силы ≈ шанс 10:1
    return 1 / (1 + 10 ** ((power_b - power_a) / spread))


def get_chances(power: float, enemy_power: float, max_draw_chance: float = 0.25) -> Chances:
    pure = get_win_chance(power, enemy_power)
    # чем ближе команды по силе, тем выше шанс ничьей
    closeness = 1 - abs(pure - 0.5) * 2
    draw = max_draw_chance * closeness
    return Chances(win=(1 - draw) * pure, draw=draw, lose=(1 - draw) * (1 - pure))


def play_match(power: float, enemy_power: float, rng: random.Random = random) -> MatchOutcome:
    chances = get_chances(power, enemy_power)
    roll = rng.random()
    if roll < chances.win:
        return MatchOutcome.REAL
    if roll < chances.win + chances.draw:
        return MatchOutcome.DRAW
    return MatchOutcome.ENEMY


def get_goals(
    min_: int,
    max_: int,
    peak: float | None = None,
    spread: float | None = None,
    rng: random.Random = random,
) -> int:
    # дискретное «гауссово» распределение голов на отрезке [min_, max_]
    if peak is None:
        peak = (min_ + max_) / 2
    if spread is None:
        spread = (max_ - min_) / 6
    goals = range(min_, max_ + 1)
    if spread == 0:
        return rng.choice(goals)
    weights = [math.exp(-((g - peak) ** 2) / (2 * spread**2)) for g in goals]
    return rng.choices(goals, weights=weights)[0]


def get_team_power(starter_powers: Sequence[int]) -> float:
    return sum(starter_powers) / len(starter_powers)


def simulate_score(power: float, enemy_power: float, rng: random.Random = random) -> Score:
    result = play_match(power, enemy_power, rng)
    if result is MatchOutcome.DRAW:
        goals = get_goals(0, 12, 2, 1.5, rng)
        return Score(goals, goals, result)
    winner = get_goals(1, 12, 2, 2, rng)
    loser = get_goals(0, winner - 1, winner / 3, 1.5, rng)
    if result is MatchOutcome.REAL:
        return Score(winner, loser, result)
    return Score(loser, winner, result)


def choose_next_enemy(not_played: Sequence[T], rng: random.Random = random) -> T:
    # фильтр по played остаётся за season — здесь только случайный выбор
    return rng.choice(not_played)


def get_points(result: MatchOutcome) -> tuple[int, int]:
    """Очки за матч: (первая команда, вторая команда)."""
    if result is MatchOutcome.REAL:
        return WIN_POINTS, LOSS_POINTS
    if result is MatchOutcome.ENEMY:
        return LOSS_POINTS, WIN_POINTS
    return DRAW_POINTS, DRAW_POINTS


def penalty_shootout(power: float, enemy_power: float, rng: random.Random = random) -> tuple[int, int]:
    """Серия пенальти после ничьей в плей-офф: (голы первой команды, голы второй).

    Сила влияет слабее, чем в игре (spread=30) — в серии многое решает удача.
    """
    winner = rng.randint(3, 5)
    loser = rng.randint(max(0, winner - 3), winner - 1)
    if rng.random() < get_win_chance(power, enemy_power, spread=30):
        return winner, loser
    return loser, winner
