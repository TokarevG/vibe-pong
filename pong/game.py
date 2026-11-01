"""Game rules that do not depend on pygame.

This module must not import pygame, so the rules can be tested without
opening a window.
"""

import itertools
import math
from enum import Enum, auto

from pong.ai import AI_SETTINGS, Difficulty
from pong.physics import (
    SERVE_SPEED,
    Ball,
    Paddle,
    bounce_velocity,
    next_speed,
    segment_hits_paddle,
)
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH

WINNING_SCORE = 11

DEFAULT_PADDLE_SPEED = 420.0
"""Paddle speed in px/s for P1, and for P2 in two-player."""


class Player(Enum):
    """The two sides of the playfield. P1 is on the left, P2 on the right."""

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


class GameEvent(Enum):
    """Something that happened during one ``Match.update`` call."""

    PADDLE_HIT = auto()
    WALL_BOUNCE = auto()
    SCORE = auto()
    VICTORY = auto()


def _other(player: Player) -> Player:
    """Return the player on the opposite side."""
    return Player.P2 if player is Player.P1 else Player.P1


MAX_WALL_TOUCHES = 1000
"""Cap on wall touches traced in one step. Past it the path is taken as one straight line."""


def _path_corners(
    before: Ball, dt: float, end_x: float, end_y: float
) -> list[tuple[float, float]]:
    """Return the corners of the ball centre's path over one step.

    The path runs from ``before`` (the state before the step) to ``(end_x, end_y)``
    (the state after it). Between wall touches it is a straight line. ``Ball.step``
    reflects the centre at each wall touch, so each touch is a corner. The corners
    are the start, each touch that falls strictly inside the step, and the end.

    A touch is at time ``t`` when the unfolded centre reaches a wall. The first
    touch is at ``(wall - y) / vy`` for the wall in the direction of motion, and the
    next ones follow every ``span / |vy|``, alternating walls. This matches
    ``Ball.step``, and nothing is sampled.

    If the step would touch walls more than ``MAX_WALL_TOUCHES`` times, the path is
    returned as the single straight line from start to end. That only happens for a
    step far longer than the game's.
    """
    corners = [(before.x, before.y)]
    top = before.radius
    bottom = PLAYFIELD_HEIGHT - before.radius
    span = bottom - top
    if before.vy != 0 and math.isfinite(dt) and span > 0:
        wall = bottom if before.vy > 0 else top
        t = (wall - before.y) / before.vy
        gap = span / abs(before.vy)
        touches = 0
        while t < dt:
            if touches == MAX_WALL_TOUCHES:
                return [corners[0], (end_x, end_y)]
            if t > 0:
                corners.append((before.x + before.vx * t, wall))
            wall = top if wall == bottom else bottom
            t += gap
            touches += 1
    corners.append((end_x, end_y))
    return corners


class Match:
    """One match: two paddles, the score, the ball and the serving state.

    The ball waits still at the centre while serving. ``start_rally`` sends it out
    toward the player who conceded the last point (P1 for the first serve).
    ``end_rally`` records a point and returns to serving.

    ``difficulty`` is stored as given. In single-player it is read once, when the
    match is built, to set P2's speed from ``AI_SETTINGS``. In two-player it is not read.

    ``update`` advances the match by one time step and reports what happened.

    ``paused`` starts ``False``. While it is ``True``, ``update`` and ``start_rally``
    do nothing. ``toggle_pause`` flips it, and does nothing once there is a winner.
    """

    def __init__(self, mode: Mode, difficulty: Difficulty) -> None:
        self.mode = mode
        self.difficulty = difficulty
        self._reset()

    def _reset(self) -> None:
        """Set the paddles, score, ball and serving state to a fresh match.

        Shared by ``__init__`` and ``restart``. Reads ``difficulty`` only in
        single-player, to set P2's speed.
        """
        p2_speed = (
            AI_SETTINGS[self.difficulty].max_speed
            if self.mode is Mode.SINGLE_PLAYER
            else DEFAULT_PADDLE_SPEED
        )
        self.p1 = Paddle(x=30, y=250, speed=DEFAULT_PADDLE_SPEED)
        self.p2 = Paddle(x=958, y=250, speed=p2_speed)
        self.score = Score()
        self.ball = Ball(BALL_CENTRE_X, BALL_CENTRE_Y, 0.0, 0.0)
        self._serving = True
        self._serve_toward = Player.P1
        self.paused = False

    def restart(self) -> None:
        """Reset to a fresh 0 to 0 match, with the ball waiting to serve.

        Clears any winner, unpauses, and puts the paddles back at their starting
        positions. The first serve goes toward P1, as in a new match. ``mode`` and
        ``difficulty`` are kept. The AI controller is not reset here; the caller
        makes a new one.
        """
        self._reset()

    @property
    def serving(self) -> bool:
        """Return ``True`` while the ball waits at the centre for a serve."""
        return self._serving

    def toggle_pause(self) -> None:
        """Pause a running match, or resume a paused one.

        Does nothing once someone has won, so the match cannot be paused after it ends.
        """
        if self.score.winner() is not None:
            return
        self.paused = not self.paused

    def start_rally(self) -> None:
        """Serve the ball toward ``_serve_toward`` at ``SERVE_SPEED`` with no vertical speed.

        Does nothing if the match is not serving, if it is paused, or if someone has
        already won.
        """
        if not self._serving or self.paused or self.score.winner() is not None:
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

    def update(
        self, dt: float, p1_direction: int, p2_direction: int
    ) -> list[GameEvent]:
        """Advance the match by ``dt`` seconds and return the events that happened.

        Both paddles move first, through ``Paddle.move``. While serving, the ball
        stays still and nothing else happens. While rallying, the ball is stepped,
        then checked for a wall bounce, a paddle hit along the step's path, and a
        point. Returns an empty list when nothing happened, and once a player has
        won it changes nothing and returns an empty list. While paused it also
        changes nothing and returns an empty list.

        ``dt`` should be at most 0.02 s, which the game loop enforces.

        Raises:
            ValueError: if a direction is not -1, 0 or 1, or ``dt`` is negative.
        """
        if self.paused or self.score.winner() is not None:
            return []

        self.p1.move(p1_direction, dt, PLAYFIELD_HEIGHT)
        self.p2.move(p2_direction, dt, PLAYFIELD_HEIGHT)

        if self._serving:
            return []

        events: list[GameEvent] = []
        # The state before the step, kept so the paddle check can sweep the path.
        before = Ball(
            self.ball.x, self.ball.y, self.ball.vx, self.ball.vy, self.ball.radius
        )
        if self.ball.step(dt, PLAYFIELD_HEIGHT):
            events.append(GameEvent.WALL_BOUNCE)

        if self.ball.vx < 0:
            hit = self._bounce_off(self.p1, 1, before, dt)
        elif self.ball.vx > 0:
            hit = self._bounce_off(self.p2, -1, before, dt)
        else:
            hit = False
        if hit:
            events.append(GameEvent.PADDLE_HIT)

        player = scorer(self.ball.x, PLAYFIELD_WIDTH)
        if player is not None:
            self.end_rally(player)
            events.append(GameEvent.SCORE)
            if self.score.winner() is not None:
                events.append(GameEvent.VICTORY)

        return events

    def _bounce_off(
        self, paddle: Paddle, direction: int, before: Ball, dt: float
    ) -> bool:
        """Bounce the ball off ``paddle`` if its path this step touches it.

        Return ``True`` if it did.

        The path runs from ``before`` (the state before the step) to the ball's
        current position, bending at wall touches (``_path_corners``). A hit is any
        segment of that path for which ``segment_hits_paddle`` is true.

        ``direction`` is the horizontal direction the ball leaves in: +1 for P1's
        paddle, -1 for P2's. The new speed is ``next_speed`` of the current speed.
        The ball is then pushed out to the face it came from (see
        ``_push_clear_of_face``), and its velocity is set as ``bounce_velocity`` gives.
        """
        corners = _path_corners(before, dt, self.ball.x, self.ball.y)
        touched = any(
            segment_hits_paddle(
                x0,
                y0,
                x1,
                y1,
                self.ball.radius,
                paddle.x,
                paddle.y,
                paddle.width,
                paddle.height,
                self.ball.vx,
            )
            for (x0, y0), (x1, y1) in itertools.pairwise(corners)
        )
        if not touched:
            return False

        half_height = paddle.height / 2
        offset = (self.ball.y - (paddle.y + half_height)) / half_height
        speed = next_speed(math.hypot(self.ball.vx, self.ball.vy))
        self.ball.vx, self.ball.vy = bounce_velocity(
            offset, speed, direction, paddle.velocity
        )
        self._push_clear_of_face(paddle, direction)
        return True

    def _push_clear_of_face(self, paddle: Paddle, direction: int) -> None:
        """Move the ball so its centre is one radius clear of the face it came from.

        ``direction`` is +1 for a P1 hit and -1 for a P2 hit. The ball came from the
        side opposite its direction before the hit, and ``Ball.step`` never changes
        ``vx``, so this is the sign of ``vx`` before the step too. For a P1 hit the
        ball's x is at least the paddle's right edge plus the radius. For a P2 hit it
        is at most the paddle's left edge minus the radius. A ball already clear of
        that face is not moved. Y is unchanged.
        """
        radius = self.ball.radius
        if direction > 0:
            self.ball.x = max(self.ball.x, paddle.x + paddle.width + radius)
        else:
            self.ball.x = min(self.ball.x, paddle.x - radius)
