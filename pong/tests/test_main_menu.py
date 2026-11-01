import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.__main__ import (
    MENU_ITEMS,
    MainMenu,
    MenuAction,
    MenuItem,
    MenuOutcome,
    MenuPage,
)
from pong.ai import Difficulty
from pong.game import Match, Mode
from pong.settings import Settings, default_settings, load_settings, save_settings

pygame = main_module.pygame

DOWN = MenuAction.DOWN
UP = MenuAction.UP
ENTER = MenuAction.ENTER
BACK = MenuAction.BACK
LEFT = MenuAction.LEFT
RIGHT = MenuAction.RIGHT


@pytest.fixture(autouse=True)
def pygame_session():
    # Each test starts and stops pygame, so a test that calls main() cannot
    # leave the others without a display or fonts.
    pygame.init()
    main_module._menu_font.cache_clear()
    main_module._digit_font.cache_clear()
    yield
    main_module._menu_font.cache_clear()
    main_module._digit_font.cache_clear()
    pygame.quit()


def _menu(tmp_path: Path, settings: Settings | None = None) -> MainMenu:
    return MainMenu(settings or default_settings(), tmp_path / "pong" / "config.json")


def _highlight(menu: MainMenu, item: MenuItem) -> None:
    """Move the highlight to ``item`` with Down presses."""
    while menu.selected is not item:
        menu.handle(DOWN)


def _has_white_in_band(surface: pygame.Surface, top: float, bottom: float) -> bool:
    for y in range(int(top), int(bottom)):
        for x in range(surface.get_width()):
            if tuple(surface.get_at((x, y)))[:3] == (255, 255, 255):
                return True
    return False


def _lit_pixels(surface: pygame.Surface) -> int:
    black = pygame.mask.from_threshold(surface, (0, 0, 0, 255), (1, 1, 1, 255))
    return surface.get_width() * surface.get_height() - black.count()


# Navigation and the initial screen


def test_opens_on_main_menu_with_start_game_highlighted(tmp_path):
    menu = _menu(tmp_path)
    assert menu.page is MenuPage.MAIN
    assert menu.selected is MenuItem.START_GAME


def test_items_are_in_the_specified_order():
    assert list(MENU_ITEMS) == [
        MenuItem.START_GAME,
        MenuItem.MODE,
        MenuItem.DIFFICULTY,
        MenuItem.CONTROLS,
        MenuItem.AUDIO,
        MenuItem.QUIT,
    ]


def test_down_moves_highlight_and_wraps_from_quit_to_start(tmp_path):
    menu = _menu(tmp_path)
    for _ in range(len(MENU_ITEMS) - 1):
        assert menu.handle(DOWN) is MenuOutcome.NONE
    assert menu.selected is MenuItem.QUIT
    assert menu.handle(DOWN) is MenuOutcome.NONE
    assert menu.selected is MenuItem.START_GAME


def test_up_wraps_from_start_to_quit(tmp_path):
    menu = _menu(tmp_path)
    assert menu.handle(UP) is MenuOutcome.NONE
    assert menu.selected is MenuItem.QUIT


def test_moving_the_highlight_does_not_activate_the_row(tmp_path):
    menu = _menu(tmp_path)
    menu.handle(DOWN)
    assert menu.selected is MenuItem.MODE
    assert menu.settings.mode is Mode.SINGLE_PLAYER
    assert not (tmp_path / "pong" / "config.json").exists()


@pytest.mark.parametrize("key", [pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_SPACE])
def test_non_navigation_keys_do_nothing_on_the_menu(tmp_path, key: int):
    menu = _menu(tmp_path)
    assert main_module._handle_menu_key(key, menu) is MenuOutcome.NONE
    assert menu.selected is MenuItem.START_GAME
    assert menu.page is MenuPage.MAIN


def test_navigation_keys_are_the_arrows_enter_and_escape():
    assert main_module._MENU_KEYS == {
        pygame.K_UP: UP,
        pygame.K_DOWN: DOWN,
        pygame.K_LEFT: LEFT,
        pygame.K_RIGHT: RIGHT,
        pygame.K_RETURN: ENTER,
        pygame.K_ESCAPE: BACK,
    }


def test_esc_on_main_menu_does_nothing(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.MODE)
    before = menu.lines()
    assert main_module._handle_menu_key(pygame.K_ESCAPE, menu) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN
    assert menu.selected is MenuItem.MODE
    assert menu.lines() == before
    assert not (tmp_path / "pong" / "config.json").exists()


# Start Game and Quit


def test_start_game_row_returns_start_outcome(tmp_path):
    menu = _menu(tmp_path)
    assert menu.handle(ENTER) is MenuOutcome.START_GAME


def test_quit_row_returns_quit_outcome(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.QUIT)
    assert menu.handle(ENTER) is MenuOutcome.QUIT


def test_start_game_creates_serving_match_with_current_mode_and_difficulty(
    tmp_path,
):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.MODE)
    menu.handle(ENTER)  # two-player
    _highlight(menu, MenuItem.DIFFICULTY)
    menu.handle(ENTER)  # hard
    _highlight(menu, MenuItem.START_GAME)
    assert menu.handle(ENTER) is MenuOutcome.START_GAME

    match, _ai = main_module._start_match(menu.settings)
    assert isinstance(match, Match)
    assert match.mode is Mode.TWO_PLAYER
    assert match.difficulty is Difficulty.HARD
    assert match.serving


# Mode


def test_enter_on_mode_toggles_and_shows_value(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.MODE)
    assert "Mode: Single-player" in menu.lines()

    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.settings.mode is Mode.TWO_PLAYER
    assert "Mode: Two-player" in menu.lines()

    menu.handle(ENTER)
    assert menu.settings.mode is Mode.SINGLE_PLAYER
    assert "Mode: Single-player" in menu.lines()


def test_mode_change_is_saved_immediately(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.MODE)
    menu.handle(ENTER)
    assert load_settings(menu.path).mode is Mode.TWO_PLAYER


# Difficulty


def test_enter_on_difficulty_cycles_easy_medium_hard(tmp_path):
    menu = _menu(tmp_path)  # starts at Medium
    _highlight(menu, MenuItem.DIFFICULTY)
    assert "Difficulty: Medium" in menu.lines()

    seen = []
    for _ in range(3):
        menu.handle(ENTER)
        seen.append(menu.settings.difficulty)
    assert seen == [Difficulty.HARD, Difficulty.EASY, Difficulty.MEDIUM]


def test_difficulty_label_follows_the_value(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.DIFFICULTY)
    menu.handle(ENTER)
    assert "Difficulty: Hard" in menu.lines()
    menu.handle(ENTER)
    assert "Difficulty: Easy" in menu.lines()


def test_difficulty_row_is_shown_in_two_player_mode(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.MODE)
    menu.handle(ENTER)
    assert menu.settings.mode is Mode.TWO_PLAYER
    assert "Difficulty: Medium" in menu.lines()


def test_difficulty_change_is_saved_immediately(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.DIFFICULTY)
    menu.handle(ENTER)
    assert load_settings(menu.path).difficulty is Difficulty.HARD


def test_mode_and_difficulty_are_restored_on_relaunch(tmp_path):
    menu = _menu(tmp_path)
    _highlight(menu, MenuItem.MODE)
    menu.handle(ENTER)
    _highlight(menu, MenuItem.DIFFICULTY)
    menu.handle(ENTER)

    relaunched = MainMenu(load_settings(menu.path), menu.path)
    assert relaunched.settings.mode is Mode.TWO_PLAYER
    assert relaunched.settings.difficulty is Difficulty.HARD


def test_failed_save_keeps_the_value_for_this_session(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("in the way")
    path = blocker / "config.json"
    assert save_settings(path, default_settings()) is False

    menu = MainMenu(default_settings(), path)
    _highlight(menu, MenuItem.MODE)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.settings.mode is Mode.TWO_PLAYER
    assert "Mode: Two-player" in menu.lines()

    _highlight(menu, MenuItem.DIFFICULTY)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.settings.difficulty is Difficulty.HARD


# Drawing


def test_draw_menu_paints_the_highlighted_line_white(tmp_path):
    # At the playfield's own size the scale is 1, so logical y is pixel y.
    surface = pygame.Surface((1000, 600))
    menu = _menu(tmp_path)
    main_module.draw_menu(surface, menu)
    assert _lit_pixels(surface) > 0
    # Row 0 is Start Game. Its band is near y = 60, row 1 is near y = 116.
    assert _has_white_in_band(surface, 40, 80)
    assert not _has_white_in_band(surface, 96, 136)

    menu.handle(DOWN)
    main_module.draw_menu(surface, menu)
    assert not _has_white_in_band(surface, 40, 80)
    assert _has_white_in_band(surface, 96, 136)


def test_draw_menu_does_nothing_for_zero_size(tmp_path):
    surface = pygame.Surface((0, 0))
    main_module.draw_menu(surface, _menu(tmp_path))


# The real loop, driven by scripted events


def _script_events(monkeypatch, frames: list[list[pygame.event.Event]]) -> None:
    """Make ``pygame.event.get`` return ``frames`` in turn, then QUIT forever."""
    queue = list(frames)

    def fake_get(*args, **kwargs):
        if queue:
            return queue.pop(0)
        return [pygame.event.Event(pygame.QUIT)]

    monkeypatch.setattr(pygame.event, "get", fake_get)


def _key(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def test_main_opens_on_menu_and_quit_row_exits_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _script_events(
        monkeypatch,
        [[_key(pygame.K_UP)], [_key(pygame.K_RETURN)]],  # Up wraps to Quit, Enter
    )
    assert main_module.main() == 0
    assert not (tmp_path / "pong" / "config.json").exists()


def test_main_esc_on_menu_keeps_running_until_quit(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _script_events(monkeypatch, [[_key(pygame.K_ESCAPE)]])
    assert main_module.main() == 0


def test_main_saves_mode_change_and_restores_it_on_next_launch(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_DOWN)],  # Mode
            [_key(pygame.K_RETURN)],  # toggle to two-player
            [_key(pygame.K_UP)],  # back to Start Game
            [_key(pygame.K_UP)],  # wraps to Quit
            [_key(pygame.K_RETURN)],  # quit
        ],
    )
    assert main_module.main() == 0
    assert load_settings(tmp_path / "pong" / "config.json").mode is Mode.TWO_PLAYER

    # Relaunch, then Start Game. The match must use the restored mode.
    started: list[Settings] = []
    real_start = main_module._start_match

    def record_start(settings: Settings):
        started.append(settings)
        return real_start(settings)

    monkeypatch.setattr(main_module, "_start_match", record_start)
    _script_events(monkeypatch, [[_key(pygame.K_RETURN)]])
    assert main_module.main() == 0
    assert started[0].mode is Mode.TWO_PLAYER


def test_main_start_game_runs_a_match_then_quits(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game
            [],
            [_key(pygame.K_SPACE)],  # starts the serve
            [],
        ],
    )
    assert main_module.main() == 0
