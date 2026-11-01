"""Game rules that do not depend on pygame.

This module must not import pygame, so the rules can be tested without
opening a window.
"""

from enum import Enum

from pong.physics import SERVE_SPEED, Ball, Paddle

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


BALL_CENTRE_X = 500.0
"""Horizontal centre of the playfield, where the ball waits between rallies."""

BALL_CENTRE_Y = 300.0
"""Vertical centre of the playfield, where the ball waits between rallies."""


class Mode(Enum):
    """How many players control the paddles."""

    SINGLE_PLAYER = 1
    TWO_PLAYER = 2


def _other(player: Player) -> Player:
    """Return the player on the opposite side."""
    return Player.P2 if player is Player.P1 else Player.P1


class Match:
    """One match: two paddles, the score, the ball and the serving state.

    The ball waits still at the centre while serving. ``start_rally`` sends it out
    toward the player who conceded the last point (P1 for the first serve).
    ``end_rally`` records a point and returns to serving.

    ``difficulty`` is stored as given and not read here. Its type should become
    ``Difficulty`` from ``pong/ai.py`` once that module exists (#16).
    """

    def __init__(self, mode: Mode, difficulty: object) -> None:
        self.mode = mode
        self.difficulty = difficulty
        self.p1 = Paddle(x=30, y=250)
        self.p2 = Paddle(x=958, y=250)
        self.score = Score()
        self.ball = Ball(BALL_CENTRE_X, BALL_CENTRE_Y, 0.0, 0.0)
        self._serving = True
        self._serve_toward = Player.P1

    @property
    def serving(self) -> bool:
        """Return ``True`` while the ball waits at the centre for a serve."""
        return self._serving

    def start_rally(self) -> None:
        """Serve the ball toward ``_serve_toward`` at ``SERVE_SPEED`` with no vertical speed.

        Does nothing if the match is not serving, or if someone has already won.
        """
        if not self._serving or self.score.winner() is not None:
            return
        direction = -1 if self._serve_toward is Player.P1 else 1
        self.ball.vx = direction * SERVE_SPEED
        self.ball.vy = 0.0
        self._serving = False

    def end_rally(self, scorer: Player) -> None:
        """Award a point to ``scorer``, centre the ball still and return to serving.

        The next serve goes toward the other player, the one who conceded.
        """
        self.score.award(scorer)
        self.ball.x = BALL_CENTRE_X
        self.ball.y = BALL_CENTRE_Y
        self.ball.vx = 0.0
        self.ball.vy = 0.0
        self._serving = True
        self._serve_toward = _other(scorer)
