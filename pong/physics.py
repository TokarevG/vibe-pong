"""Core game objects and their movement rules.

This module has no pygame dependency, so the rules can be tested without a window.
Coordinates are logical pixels with the y axis pointing down: a larger ``y`` is
lower on screen.
"""

import math

MAX_BOUNCE_ANGLE_DEGREES = 60.0
"""Angle from horizontal, in degrees, for a hit at the paddle's far edge."""

PADDLE_INFLUENCE = 0.25
"""Fraction of the paddle's vertical velocity added to the ball's vertical velocity."""

SERVE_SPEED = 300.0
"""Ball speed in px/s when a rally starts."""

SPEED_GAIN = 1.05
"""Multiplier applied to the ball's speed after each paddle hit."""

MAX_SPEED = 900.0
"""Upper limit on the ball's speed in px/s."""


def next_speed(speed: float) -> float:
    """Return the ball's speed after one paddle hit, capped at ``MAX_SPEED``.

    The result is ``speed * SPEED_GAIN``, or ``MAX_SPEED`` if that is larger.
    The result is never above ``MAX_SPEED``, so a speed already at or above the
    cap stays at ``MAX_SPEED``. ``inf`` gives ``MAX_SPEED``.

    Raises:
        ValueError: if ``speed`` is ``nan``. ``nan`` has no ordering, so no cap
            can be applied to it.
    """
    if math.isnan(speed):
        raise ValueError("speed must be a number, got nan")
    return min(speed * SPEED_GAIN, MAX_SPEED)


def bounce_velocity(
    offset: float, speed: float, direction: int, paddle_vy: float = 0.0
) -> tuple[float, float]:
    """Return the ball's ``(vx, vy)`` after a paddle hit, from the impact position.

    ``offset`` is the normalized impact position on the paddle: -1 at the top
    edge, 0 at the centre and 1 at the bottom edge. Values outside [-1, 1] are
    clamped to that range. The angle from horizontal is
    ``offset * MAX_BOUNCE_ANGLE_DEGREES``, so ``vx = direction * speed * cos(angle)``
    and ``vy = speed * sin(angle)``. Negative ``vy`` moves the ball up the screen.

    ``paddle_vy`` is the paddle's vertical velocity at impact in px/s, positive
    down the screen. It adds ``PADDLE_INFLUENCE * paddle_vy`` to ``vy``, and the
    result is then scaled so the speed is still ``speed``. The sign of ``vx`` is
    never changed by ``paddle_vy``. With ``paddle_vy == 0`` the result is the
    same as without it. The speed is preserved: ``sqrt(vx**2 + vy**2) == speed``.

    Raises:
        ValueError: if ``direction`` is not +1 or -1, ``speed`` is negative, or
            ``paddle_vy`` is not finite.
    """
    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 or -1, got {direction}")
    if speed < 0:
        raise ValueError(f"speed must not be negative, got {speed}")
    if not math.isfinite(paddle_vy):
        raise ValueError(f"paddle_vy must be finite, got {paddle_vy}")

    clamped = min(max(offset, -1.0), 1.0)
    angle = math.radians(clamped * MAX_BOUNCE_ANGLE_DEGREES)
    vx = direction * speed * math.cos(angle)
    vy = speed * math.sin(angle)
    if paddle_vy == 0:
        return vx, vy

    vy += PADDLE_INFLUENCE * paddle_vy
    magnitude = math.hypot(vx, vy)
    # magnitude is zero only when speed is zero, so the ball stays still.
    scale = speed / magnitude if magnitude > 0 else 0.0
    return vx * scale, vy * scale


def _travel(velocity: float, dt: float) -> float:
    """Distance covered at ``velocity`` for ``dt``, with no travel at zero velocity.

    The zero check keeps ``0 * inf`` from producing ``nan``.
    """
    return 0.0 if velocity == 0 else velocity * dt


class Paddle:
    """A vertical paddle whose ``y`` is kept inside the playfield.

    ``x`` is the left edge and ``y`` is the top edge. After each ``move``,
    ``velocity`` holds the vertical velocity actually applied, in px/s.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: float = 12,
        height: float = 100,
        speed: float = 420.0,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)
        self.speed = float(speed)
        self.velocity = 0.0

    def move(self, direction: int, dt: float, playfield_height: float) -> None:
        """Move up (-1), stay (0) or move down (1) for ``dt`` seconds.

        The paddle moves ``direction * speed * dt`` pixels and is clamped so that
        ``0 <= y`` and ``y + height <= playfield_height``.

        Raises:
            ValueError: if ``direction`` is not -1, 0 or 1, or ``dt`` is negative.
        """
        if direction not in (-1, 0, 1):
            raise ValueError(f"direction must be -1, 0 or 1, got {direction}")
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")

        if direction == 0:
            self.velocity = 0.0
            return

        old_y = self.y
        target_y = old_y + direction * self.speed * dt
        max_y = playfield_height - self.height
        self.y = min(max(target_y, 0.0), max_y)

        self.velocity = (self.y - old_y) / dt if dt > 0 else 0.0


class Ball:
    """A ball whose ``x`` and ``y`` are its centre, bouncing off the top and bottom.

    ``vx`` and ``vy`` are in px/s. The ball's centre stays within
    ``[radius, playfield_height - radius]`` on the y axis.
    """

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        radius: float = 8,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.radius = float(radius)

    def step(self, dt: float, playfield_height: float) -> bool:
        """Advance the ball by ``dt`` seconds and bounce it off the top and bottom walls.

        The ball moves by ``(vx * dt, vy * dt)``. Each time the centre goes past a
        wall it is reflected back across that wall and ``vy`` flips sign. ``vx`` is
        never changed by a bounce. Returns ``True`` if at least one wall bounce
        happened during this step, otherwise ``False``.

        The reflections are computed in constant time, so a very large ``dt`` is
        cheap. An infinite travel (``dt`` infinite with nonzero velocity, or an
        overflow) has no finite resting point, so the centre is put on the wall it
        was heading for.

        Raises:
            ValueError: if ``dt`` is negative or ``nan``, or the playfield is not a
                finite height greater than the ball's diameter
                (``playfield_height > 2 * radius``).
        """
        if math.isnan(dt):
            raise ValueError("dt must be a number, got nan")
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")
        if not math.isfinite(playfield_height) or playfield_height <= 2 * self.radius:
            raise ValueError(
                f"playfield height must be finite and greater than 2 * radius, "
                f"got {playfield_height} for radius {self.radius}"
            )

        self.x += _travel(self.vx, dt)

        top = self.radius
        bottom = playfield_height - self.radius
        span = bottom - top
        travel = _travel(self.vy, dt)
        y_raw = self.y + travel

        # Position relative to the top wall, before any reflection.
        offset = y_raw - top
        ratio = offset / span if math.isfinite(y_raw) else math.inf
        if not math.isfinite(ratio):
            self.y = bottom if travel > 0 else top
            return True

        # Each reflection is a fold back into [top, bottom]. Folding the unbounded
        # line with period 2 * span gives the same point as reflecting one wall
        # at a time, and the number of folds sets the sign of vy.
        if offset >= 0:
            bounces = max(0, math.ceil(ratio) - 1)
        else:
            bounces = math.ceil(-ratio)

        phase = offset % (2 * span)
        if phase > span:
            phase = 2 * span - phase
        self.y = min(max(top + phase, top), bottom)

        if bounces % 2 == 1:
            self.vy = -self.vy
        return bounces > 0


def ball_hits_paddle(
    ball_x: float,
    ball_y: float,
    ball_radius: float,
    paddle_x: float,
    paddle_y: float,
    paddle_w: float,
    paddle_h: float,
    ball_vx: float,
) -> bool:
    """Return ``True`` if the ball touches the paddle while moving toward it.

    ``(paddle_x, paddle_y)`` is the paddle's top-left corner. The paddle is on the
    left when its centre ``x`` (``paddle_x + paddle_w / 2``) is less than the
    playfield midline at ``x == 500``, otherwise on the right. The side depends on
    the paddle only, not on the ball, so a fast ball whose centre has already
    crossed the paddle's centre in one step can still be hit. A hit needs
    ``ball_vx < 0`` for a paddle on the left and ``ball_vx > 0`` for a paddle on
    the right, so ``ball_vx == 0`` is never a hit.

    The ball overlaps the paddle when the distance from the ball centre to the
    nearest point of the paddle rectangle is at most ``ball_radius``. A distance
    exactly equal to the radius counts as a hit.

    This function does not change any state.
    """
    if not _paddle_faces_ball(paddle_x, paddle_w, ball_vx):
        return False

    distance_sq = _point_rect_distance_sq(
        ball_x, ball_y, paddle_x, paddle_y, paddle_x + paddle_w, paddle_y + paddle_h
    )
    return distance_sq <= ball_radius * ball_radius


def _paddle_faces_ball(paddle_x: float, paddle_w: float, ball_vx: float) -> bool:
    """Return ``True`` if ``ball_vx`` points toward the paddle's side of the playfield.

    The paddle is on the left when its centre ``x`` is less than 500, otherwise on
    the right. The left paddle needs ``ball_vx < 0``, the right one ``ball_vx > 0``.
    """
    paddle_on_left = paddle_x + paddle_w / 2 < 500
    if paddle_on_left:
        return ball_vx < 0
    return ball_vx > 0


def _point_rect_distance_sq(
    px: float, py: float, x0: float, y0: float, x1: float, y1: float
) -> float:
    """Return the squared distance from ``(px, py)`` to the rectangle ``[x0, x1] x [y0, y1]``."""
    nearest_x = min(max(px, x0), x1)
    nearest_y = min(max(py, y0), y1)
    dx = px - nearest_x
    dy = py - nearest_y
    return dx * dx + dy * dy


def _point_segment_distance_sq(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Return the squared distance from ``(px, py)`` to the segment ``a``-``b``.

    A zero-length segment is treated as the single point ``a``.
    """
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        t = 0.0
    else:
        t = min(max(((px - ax) * dx + (py - ay) * dy) / length_sq, 0.0), 1.0)
    cx = ax + t * dx
    cy = ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def _segment_crosses_rect(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> bool:
    """Return ``True`` if the segment ``a``-``b`` meets the closed rectangle.

    Liang-Barsky clipping: the segment is kept as ``a + t * (b - a)`` for ``t`` in
    ``[0, 1]``, cut down by each of the four edge half-planes.
    """
    dx = bx - ax
    dy = by - ay
    t_enter = 0.0
    t_exit = 1.0
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t_enter = max(t_enter, t)
        else:
            t_exit = min(t_exit, t)
        if t_enter > t_exit:
            return False
    return True


def segment_hits_paddle(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    ball_radius: float,
    paddle_x: float,
    paddle_y: float,
    paddle_w: float,
    paddle_h: float,
    ball_vx: float,
) -> bool:
    """Return ``True`` if a ball centre moving along the segment touches the paddle.

    The segment runs from ``(x0, y0)`` to ``(x1, y1)``, the ball centre before and
    after a straight move. The paddle is the same as in ``ball_hits_paddle``, and
    so is the side and direction rule: ``ball_vx`` must point toward the paddle's
    side, and it is the velocity that applies to the whole segment.

    The result is exact. The ball touches the paddle at some point of the segment
    exactly when the distance from the segment to the paddle rectangle is at most
    ``ball_radius``. For two convex shapes that do not overlap, that distance is
    the least of two sets: the distance from each endpoint to the rectangle, and
    the distance from each rectangle corner to the segment. If the segment meets
    the rectangle, the distance is zero and the result is ``True``.

    This function does not change any state.
    """
    if not _paddle_faces_ball(paddle_x, paddle_w, ball_vx):
        return False

    rect_x1 = paddle_x + paddle_w
    rect_y1 = paddle_y + paddle_h
    if _segment_crosses_rect(x0, y0, x1, y1, paddle_x, paddle_y, rect_x1, rect_y1):
        return True

    candidates = [
        _point_rect_distance_sq(x0, y0, paddle_x, paddle_y, rect_x1, rect_y1),
        _point_rect_distance_sq(x1, y1, paddle_x, paddle_y, rect_x1, rect_y1),
    ]
    for cx, cy in (
        (paddle_x, paddle_y),
        (rect_x1, paddle_y),
        (paddle_x, rect_y1),
        (rect_x1, rect_y1),
    ):
        candidates.append(_point_segment_distance_sq(cx, cy, x0, y0, x1, y1))
    return min(candidates) <= ball_radius * ball_radius
