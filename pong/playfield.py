"""Scale and centre the fixed 1000 x 600 playfield inside a resizable window.

This module is pure geometry and must not import pygame, so it can be tested
without opening a window.
"""

PLAYFIELD_WIDTH = 1000
PLAYFIELD_HEIGHT = 600


def fit_playfield(window_w: float, window_h: float) -> tuple[float, float, float]:
    """Return ``(scale, offset_x, offset_y)`` that fit the playfield in the window.

    The playfield's on-screen size is ``1000 * scale`` by ``600 * scale`` and its
    top-left corner is at ``(offset_x, offset_y)`` in window pixels. The scale is
    uniform, so the 5:3 aspect ratio is kept, and the leftover space is split
    evenly on both sides (black margins).

    Raises:
        ValueError: if the window width or height is 0 or less.
    """
    if not (window_w > 0 and window_h > 0):
        raise ValueError(f"window size must be positive, got {window_w} x {window_h}")

    scale = min(window_w / PLAYFIELD_WIDTH, window_h / PLAYFIELD_HEIGHT)
    offset_x = (window_w - PLAYFIELD_WIDTH * scale) / 2
    offset_y = (window_h - PLAYFIELD_HEIGHT * scale) / 2
    return float(scale), float(offset_x), float(offset_y)
