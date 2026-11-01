"""Headless checks of the window resize path.

A real edge drag cannot be simulated under ``SDL_VIDEODRIVER=dummy``. These tests
resize the window through pygame's window object instead, then check that the
display surface follows the new size, that the playfield keeps its 5:3 shape
with equal black bars, and that the window origin does not move.
"""

import importlib
import os
import warnings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.ai import Difficulty
from pong.game import Match, Mode
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH, fit_playfield
from pong.settings import default_settings

pygame = main_module.pygame


@pytest.fixture
def window():
    pygame.init()
    surface = pygame.display.set_mode((1000, 600), pygame.RESIZABLE)
    with warnings.catch_warnings():
        # Window.from_display_module is deprecated in pygame-ce but is the only
        # way to resize the window from a test. The submodule is loaded by name,
        # so this file has no import statement for pygame.
        warnings.simplefilter("ignore", DeprecationWarning)
        video = importlib.import_module("pygame._sdl2.video")
        win = video.Window.from_display_module()
    yield surface, win
    pygame.quit()


def _resize(win, size: tuple[int, int]) -> None:
    win.size = size
    pygame.event.pump()
    pygame.event.get()


def test_display_surface_follows_window_size(window):
    _, win = window
    _resize(win, (1200, 700))
    surface = pygame.display.get_surface()
    assert surface.get_size() == (1200, 700)
    assert win.size == (1200, 700)


def test_window_origin_is_kept_after_resize(window):
    _, win = window
    win.position = (300, 200)
    before = win.position
    _resize(win, (1300, 900))
    assert win.position == before


def test_resized_playfield_keeps_5_3_with_equal_bars(window):
    _, win = window
    _resize(win, (1200, 900))
    width, height = pygame.display.get_surface().get_size()
    scale, offset_x, offset_y = fit_playfield(width, height)
    # Wide enough to fill the width, so the bars are on the top and bottom.
    assert scale == pytest.approx(1.2)
    assert offset_x == pytest.approx(0.0)
    top_bar = offset_y
    bottom_bar = height - offset_y - PLAYFIELD_HEIGHT * scale
    assert top_bar == pytest.approx(bottom_bar)
    assert PLAYFIELD_WIDTH * scale == pytest.approx(width)


def test_draw_after_resize_leaves_black_bars(window):
    _, win = window
    _resize(win, (1200, 900))
    surface = pygame.display.get_surface()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    main_module.draw_frame(surface, match)
    # The top bar is black at the middle of the top edge.
    assert tuple(surface.get_at((600, 0)))[:3] == (0, 0, 0)
    # The bottom bar is black at the middle of the bottom edge.
    assert tuple(surface.get_at((600, 899)))[:3] == (0, 0, 0)


def test_shrinking_to_a_tiny_window_draws_without_error(window, tmp_path):
    _, win = window
    _resize(win, (120, 80))
    surface = pygame.display.get_surface()
    assert surface.get_size() == (120, 80)
    main_module.draw_frame(surface, Match(Mode.TWO_PLAYER, Difficulty.MEDIUM))
    menu = main_module.MainMenu(default_settings(), tmp_path / "settings.json")
    main_module.draw_menu(surface, menu)
