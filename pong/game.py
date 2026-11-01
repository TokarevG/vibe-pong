"""Game rules that do not depend on pygame.

This module must not import pygame, so the rules can be tested without
opening a window.
"""

from enum import Enum

WINNING_SCORE = 11


class Player(Enum):
    """The two sides of the playfield. P1 is on the right, P2 on the left."""

    P1 = 1
    P2 = 2


class Score:
    """Points for each player, and the winner once someone reaches ``WINNING_SCORE``.

    Counting continues after a win. The winner is fixed to the first player who
    reached ``WINNING_SCORE``; stopping the match is the job of ``Match``.
    """

    def __init__(self) -> None:
        self._points: dict[Player, int] = {Player.P1: 0, Player.P2: 0}
        self._winner: Player | None = None

    def award(self, player: Player) -> None:
        """Add one point to ``player`` and record the winner if this reaches the target."""
        self._points[player] += 1
        if self._winner is None and self._points[player] >= WINNING_SCORE:
            self._winner = player

    def points(self, player: Player) -> int:
        """Return how many points ``player`` has."""
        return self._points[player]

    def winner(self) -> Player | None:
        """Return the player who reached ``WINNING_SCORE`` first, or ``None``."""
        return self._winner


def scorer(ball_x: float, playfield_width: float) -> Player | None:
    """Return the player who scores when the ball's centre leaves the field.

    The ball's centre is compared against the edges. A point goes to P2 when the
    centre is strictly past the left edge (``ball_x < 0``), and to P1 when it is
    strictly past the right edge (``ball_x > playfield_width``). Otherwise, including
    when the centre is exactly on an edge, return ``None``.
    """
    if ball_x < 0:
        return Player.P2
    if ball_x > playfield_width:
        return Player.P1
    return None
