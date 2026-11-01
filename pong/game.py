"""Game rules that do not depend on pygame.

This module must not import pygame, so the rules can be tested without
opening a window.
"""

import math
from enum import Enum, auto

from pong.ai import AI_SETTINGS, Difficulty
from pong.physics import (
    SERVE_SPEED,
    Ball,
    Paddle,
    ball_hits_paddle,
    bounce_velocity,
    next_speed,
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


SWEEP_SPACING = 0.5
"""Largest gap between sampled ball centres in one step, in ball radii."""

MAX_SWEEP_SAMPLES = 1000
"""Cap on the samples in one step, so an extreme ``dt`` cannot make the work unbounded."""


def _centres_along_step(
    ball: Ball, dt: float, crossing_x: float
) -> list[tuple[float, float]]:
    """Return ball centres sampled along one step, from the state ``ball`` is in.

    The samples are at times ``0, dt/n, 2*dt/n, ..., dt``. The ball's speed is
    constant over the step, so neighbouring samples are ``speed * dt / n`` apart
    along the path. ``n`` is chosen so that gap is at most ``SWEEP_SPACING`` times
    the radius. Each sample comes from a copy of ``ball`` stepped to that time, so a
    wall bounce inside the step is followed. The time the centre crosses
    ``crossing_x`` is added as one more sample when it falls inside the step.

    Why this covers the path: the centres that touch a paddle form a convex
    region (the paddle rectangle grown by the radius). Where a straight path
    passes through that region, the piece inside it is at least one sample gap
    long, unless the path just clips a rounded corner of it. A clip of that kind is
    shallower than about ``radius / 32`` (a quarter of a pixel for radius 8). So a
    hit is missed only when the ball grazes a corner that shallowly.
    """
    spacing = SWEEP_SPACING * ball.radius
    distance = math.hypot(ball.vx, ball.vy) * dt
    if distance / spacing < MAX_SWEEP_SAMPLES:
        count = max(1, math.ceil(distance / spacing))
    else:
        count = MAX_SWEEP_SAMPLES

    times = [0.0] + [dt * i / count for i in range(1, count + 1)]
    if ball.vx != 0:
        crossing_t = (crossing_x - ball.x) / ball.vx
        if 0 < crossing_t <= dt:
            times.append(crossing_t)

    centres: list[tuple[float, float]] = []
    for t in times:
        if t <= 0:
            centres.append((ball.x, ball.y))
            continue
        probe = Ball(ball.x, ball.y, ball.vx, ball.vy, ball.radius)
        probe.step(t, PLAYFIELD_HEIGHT)
        centres.append((probe.x, probe.y))
    return centres


class Match:
    """One match: two paddles, the score, the ball and the serving state.

    The ball waits still at the centre while serving. ``start_rally`` sends it out
    toward the player who conceded the last point (P1 for the first serve).
    ``end_rally`` records a point and returns to serving.

    ``difficulty`` is stored as given. In single-player it is read once, when the
    match is built, to set P2's speed from ``AI_SETTINGS``. In two-player it is not read.

    ``update`` advances the match by one time step and reports what happened.
    """

    def __init__(self, mode: Mode, difficulty: Difficulty) -> None:
        self.mode = mode
        self.difficulty = difficulty
        p2_speed = (
            AI_SETTINGS[difficulty].max_speed
            if mode is Mode.SINGLE_PLAYER
            else DEFAULT_PADDLE_SPEED
        )
        self.p1 = Paddle(x=30, y=250, speed=DEFAULT_PADDLE_SPEED)
        self.p2 = Paddle(x=958, y=250, speed=p2_speed)
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

    def update(
        self, dt: float, p1_direction: int, p2_direction: int
    ) -> list[GameEvent]:
        """Advance the match by ``dt`` seconds and return the events that happened.

        Both paddles move first, through ``Paddle.move``. While serving, the ball
        stays still and nothing else happens. While rallying, the ball is stepped,
        then checked for a wall bounce, a paddle hit along the step's path, and a
        point. Returns an empty list when nothing happened, and once a player has
        won it changes nothing and returns an empty list.

        ``dt`` should be at most 0.02 s, which the game loop enforces.

        Raises:
            ValueError: if a direction is not -1, 0 or 1, or ``dt`` is negative.
        """
        if self.score.winner() is not None:
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
        current position, sampled by ``_centres_along_step``. A hit is any sample
        for which ``ball_hits_paddle`` is true.

        ``direction`` is the horizontal direction the ball leaves in: +1 for P1's
        paddle, -1 for P2's. The new speed is ``next_speed`` of the current speed.
        The ball keeps its position.
        """
        touched = any(
            ball_hits_paddle(
                x,
                y,
                self.ball.radius,
                paddle.x,
                paddle.y,
                paddle.width,
                paddle.height,
                self.ball.vx,
            )
            for x, y in _centres_along_step(before, dt, paddle.x + paddle.width / 2)
        )
        if not touched:
            return False

        half_height = paddle.height / 2
        offset = (self.ball.y - (paddle.y + half_height)) / half_height
        speed = next_speed(math.hypot(self.ball.vx, self.ball.vy))
        self.ball.vx, self.ball.vy = bounce_velocity(
            offset, speed, direction, paddle.velocity
        )
        return True
