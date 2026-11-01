"""AI opponent tuning for the single-player game.

This module must not import pygame, so the tuning can be tested without a window.
The values here are starting points and may change during playtesting.
"""

from dataclasses import dataclass
from enum import Enum


class Difficulty(Enum):
    """How capable the AI opponent is. ``EASY`` is the least capable."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class AISettings:
    """Tuning for one difficulty level.

    Attributes:
        reaction_delay: seconds between the ball changing direction and the AI
            reacting to it.
        max_speed: fastest the AI paddle can move, in px/s.
        aim_error: how far off centre the AI aims, in px.
    """

    reaction_delay: float
    max_speed: float
    aim_error: float


AI_SETTINGS: dict[Difficulty, AISettings] = {
    Difficulty.EASY: AISettings(reaction_delay=0.40, max_speed=240.0, aim_error=60.0),
    Difficulty.MEDIUM: AISettings(reaction_delay=0.25, max_speed=330.0, aim_error=30.0),
    Difficulty.HARD: AISettings(reaction_delay=0.10, max_speed=420.0, aim_error=10.0),
}
"""Tuning values for each difficulty. This is the only place they are defined."""
