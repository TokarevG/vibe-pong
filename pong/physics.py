"""Core game objects and their movement rules.

This module must not import pygame, so the rules can be tested without a window.
Coordinates are logical pixels with the y axis pointing down: a larger ``y`` is
lower on screen.
"""


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

        Raises:
            ValueError: if ``dt`` is negative, or the playfield is not taller than
                the ball's diameter (``playfield_height <= 2 * radius``).
        """
        if dt < 0:
            raise ValueError(f"dt must not be negative, got {dt}")
        if playfield_height <= 2 * self.radius:
            raise ValueError(
                f"playfield height must be greater than 2 * radius, "
                f"got {playfield_height} for radius {self.radius}"
            )

        self.x += self.vx * dt
        y_raw = self.y + self.vy * dt

        top = self.radius
        bottom = playfield_height - self.radius
        bounced = False
        while y_raw < top or y_raw > bottom:
            bounced = True
            if y_raw < top:
                y_raw = 2 * top - y_raw
            else:
                y_raw = 2 * bottom - y_raw
            self.vy = -self.vy

        self.y = y_raw
        return bounced
