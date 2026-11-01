"""Entry point: open the Pong window and run the frame loop at 60 FPS.

Run with ``python -m pong``. This is the only module that imports pygame.
"""

import functools
import sys

import pygame

from pong.ai import Difficulty
from pong.game import Match, Mode, Player
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH, fit_playfield

FPS = 60
# Longest step the simulation may take in one frame, so a slow frame cannot
# let the ball pass through a paddle.
MAX_DT = 0.02

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

CENTRE_LINE_X = 500.0
"""Horizontal position of the dashed centre line, in logical units."""
CENTRE_LINE_WIDTH = 4.0
DASH_LENGTH = 20.0
DASH_GAP = 20.0

SCORE_X = {Player.P1: 250.0, Player.P2: 750.0}
"""Horizontal centre of each player's score, in logical units."""
SCORE_TOP = 40.0
"""Distance from the top of the playfield to the top of the score digits."""
DIGIT_FONT_SIZE = 80
"""Font size in logical units. At this size a digit is about 40 units tall."""


@functools.lru_cache(maxsize=16)
def _digit_font(size: int) -> pygame.font.Font:
    """Return the default font at ``size`` pixels, cached by size."""
    return pygame.font.Font(None, size)


def _screen_rect(
    left: float,
    top: float,
    right: float,
    bottom: float,
    scale: float,
    offset_x: float,
    offset_y: float,
) -> pygame.Rect:
    """Map a logical rectangle to window pixels.

    Each edge is rounded separately, so neighbouring rectangles share an edge
    with no gap or overlap.
    """
    x0 = round(offset_x + left * scale)
    y0 = round(offset_y + top * scale)
    x1 = round(offset_x + right * scale)
    y1 = round(offset_y + bottom * scale)
    return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


def draw_frame(surface: pygame.Surface, match: Match) -> None:
    """Draw one frame of ``match`` onto ``surface``.

    The whole surface is filled with black first. The playfield is scaled and
    centred with ``fit_playfield``, so the 5:3 shape is kept and the leftover
    space is black. Nothing is drawn, and ``fit_playfield`` is not called, when
    the width or height is 0. Only reads ``match``.
    """
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return

    scale, offset_x, offset_y = fit_playfield(width, height)
    surface.fill(BLACK)

    half_line = CENTRE_LINE_WIDTH / 2
    top = 0.0
    while top < PLAYFIELD_HEIGHT:
        bottom = min(top + DASH_LENGTH, PLAYFIELD_HEIGHT)
        dash = _screen_rect(
            CENTRE_LINE_X - half_line,
            top,
            CENTRE_LINE_X + half_line,
            bottom,
            scale,
            offset_x,
            offset_y,
        )
        pygame.draw.rect(surface, WHITE, dash)
        top += DASH_LENGTH + DASH_GAP

    for paddle in (match.p1, match.p2):
        rect = _screen_rect(
            paddle.x,
            paddle.y,
            paddle.x + paddle.width,
            paddle.y + paddle.height,
            scale,
            offset_x,
            offset_y,
        )
        pygame.draw.rect(surface, WHITE, rect)

    centre = (
        round(offset_x + match.ball.x * scale),
        round(offset_y + match.ball.y * scale),
    )
    pygame.draw.circle(surface, WHITE, centre, max(1, round(match.ball.radius * scale)))

    font = _digit_font(max(1, round(DIGIT_FONT_SIZE * scale)))
    for player, x in SCORE_X.items():
        digits = font.render(str(match.score.points(player)), True, WHITE)
        # Place the visible glyph, not the text box, so its centre sits on x and
        # its top sits SCORE_TOP from the top of the playfield.
        glyph = digits.get_bounding_rect()
        surface.blit(
            digits,
            (
                round(offset_x + x * scale - glyph.centerx),
                round(offset_y + SCORE_TOP * scale - glyph.y),
            ),
        )


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode(
        (PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT), pygame.RESIZABLE
    )
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)

    running = True
    while running:
        # Seconds since the previous frame, capped at MAX_DT. Nothing consumes
        # it yet; the movement step will use it once it exists.
        _dt = min(clock.tick(FPS) / 1000.0, MAX_DT)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE and event.w > 0 and event.h > 0:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        draw_frame(screen, match)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
