"""Game rules that do not depend on pygame.

This module must not import pygame, so the rules can be tested without
opening a window.
"""

from enum import Enum


class Player(Enum):
    """The two sides of the playfield. P1 is on the right, P2 on the left."""

    P1 = 1
    P2 = 2


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
