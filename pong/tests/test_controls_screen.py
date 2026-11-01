import json
import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.__main__ import (
    MainMenu,
    MenuAction,
    MenuItem,
    MenuOutcome,
    MenuPage,
)
from pong.ai import AIController, Difficulty
from pong.game import Match, Mode
from pong.settings import (
    Settings,
    default_settings,
    find_binding_conflicts,
    load_settings,
    save_settings,
)

pygame = main_module.pygame

DOWN = MenuAction.DOWN
UP = MenuAction.UP
ENTER = MenuAction.ENTER
BACK = MenuAction.BACK

DEFAULT_LINES = [
    "Player 1 up: W",
    "Player 1 down: S",
    "Player 2 up: UP",
    "Player 2 down: DOWN",
    "Back",
    "",
]


@pytest.fixture(autouse=True)
def pygame_session():
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
    while menu.selected is not item:
        menu.handle(DOWN)


def _open_controls(menu: MainMenu) -> None:
    """Open the Controls screen from the main menu, as the player does."""
    _highlight(menu, MenuItem.CONTROLS)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.page is MenuPage.CONTROLS


def _select_row(menu: MainMenu, row: int) -> None:
    """Move the Controls highlight down to ``row``. Row 0 is Player 1 up."""
    for _ in range(row):
        menu.handle(DOWN)


def _wait_for_row(menu: MainMenu, row: int) -> None:
    """Select ``row`` and press Enter, so the screen waits for a key."""
    _select_row(menu, row)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.capturing


def _press(menu: MainMenu, key: int) -> MenuOutcome:
    """Send a KEYDOWN key code to the menu, as the game loop does."""
    return main_module._handle_menu_key(key, menu)


def _config_file(tmp_path: Path) -> Path:
    return tmp_path / "pong" / "config.json"


class _Keys:
    """Stands in for ``pygame.key.get_pressed()`` with the given key codes held."""

    def __init__(self, *held: int) -> None:
        self._held = set(held)

    def __getitem__(self, key_code: int) -> bool:
        return key_code in self._held


def _script_events(monkeypatch, frames: list[list[pygame.event.Event]]) -> None:
    queue = list(frames)

    def fake_get(*args, **kwargs):
        if queue:
            return queue.pop(0)
        return [pygame.event.Event(pygame.QUIT)]

    monkeypatch.setattr(pygame.event, "get", fake_get)


def _key(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


# Screen contents and navigation


def test_controls_opens_from_main_menu_with_four_rows_and_back(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    assert menu.lines() == DEFAULT_LINES


def test_rows_show_the_current_key_names(tmp_path):
    settings = default_settings()
    settings.bindings = {
        "p1_up": "i",
        "p1_down": "k",
        "p2_up": "left shift",
        "p2_down": "space",
    }
    menu = _menu(tmp_path, settings)
    _open_controls(menu)
    assert menu.lines()[:4] == [
        "Player 1 up: I",
        "Player 1 down: K",
        "Player 2 up: LEFT SHIFT",
        "Player 2 down: SPACE",
    ]


def test_down_and_up_move_the_highlight_and_wrap_over_five_rows(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    assert menu.highlighted_line == 0
    for expected in (1, 2, 3, 4, 0):
        menu.handle(DOWN)
        assert menu.highlighted_line == expected
    menu.handle(UP)
    assert menu.highlighted_line == 4


def test_navigation_moves_do_not_wait_for_a_key(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _select_row(menu, 2)
    assert not menu.capturing
    assert menu.lines() == DEFAULT_LINES


# Waiting for a key


def test_enter_on_a_row_shows_press_a_key_and_waits(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    assert menu.lines()[0] == "Player 1 up: Press a key"
    assert menu.lines()[1:4] == DEFAULT_LINES[1:4]


def test_next_key_press_becomes_the_binding_and_the_wait_ends(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    assert _press(menu, pygame.K_i) is MenuOutcome.NONE
    assert not menu.capturing
    assert menu.settings.bindings["p1_up"] == "i"
    assert menu.lines()[0] == "Player 1 up: I"


def test_key_names_are_stored_as_pygame_reports_them(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 3)
    _press(menu, pygame.K_LSHIFT)
    assert menu.settings.bindings["p2_down"] == "left shift"


def test_a_key_pygame_cannot_name_is_ignored_and_the_wait_goes_on(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    menu.capture("")
    assert menu.capturing
    assert menu.settings.bindings["p1_up"] == "w"
    assert not _config_file(tmp_path).exists()


def test_enter_and_arrow_keys_are_bound_as_ordinary_keys_while_waiting(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 1)
    _press(menu, pygame.K_RETURN)
    assert menu.settings.bindings["p1_down"] == "return"
    assert menu.page is MenuPage.CONTROLS


# Esc


def test_esc_cancels_the_wait_and_leaves_the_binding_unchanged(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    assert _press(menu, pygame.K_ESCAPE) is MenuOutcome.NONE
    assert not menu.capturing
    assert menu.page is MenuPage.CONTROLS
    assert menu.settings.bindings["p1_up"] == "w"
    assert menu.lines() == DEFAULT_LINES
    assert not _config_file(tmp_path).exists()


def test_esc_cannot_be_bound_it_only_cancels_the_wait(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 2)
    menu.capture("escape")
    assert not menu.capturing
    assert "escape" not in menu.settings.bindings.values()
    assert menu.settings.bindings["p2_up"] == "up"
    assert not _config_file(tmp_path).exists()


def test_esc_when_not_waiting_returns_to_the_main_menu(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    assert _press(menu, pygame.K_ESCAPE) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN
    assert menu.selected is MenuItem.CONTROLS


def test_back_row_returns_to_the_main_menu(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _select_row(menu, 4)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN
    assert menu.selected is MenuItem.CONTROLS


def test_enter_on_back_does_not_wait_for_a_key(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _select_row(menu, 4)
    menu.handle(ENTER)
    assert not menu.capturing


def test_esc_on_the_back_row_returns_to_the_main_menu(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _select_row(menu, 4)
    assert _press(menu, pygame.K_ESCAPE) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN


# Conflicts


def test_key_used_by_another_action_is_rejected_with_its_name(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 1)  # Player 1 down
    _press(menu, pygame.K_w)  # used by Player 1 up
    assert menu.lines()[1] == "Player 1 down: S"
    assert menu.lines()[5] == "W is already used by Player 1 up"
    assert menu.settings.bindings["p1_down"] == "s"
    assert not _config_file(tmp_path).exists()


@pytest.mark.parametrize(
    ("row", "key", "holder"),
    [
        (2, pygame.K_s, "Player 1 down"),
        (3, pygame.K_w, "Player 1 up"),
        (0, pygame.K_DOWN, "Player 2 down"),
        (1, pygame.K_UP, "Player 2 up"),
    ],
)
def test_conflict_message_names_the_holder_for_any_pair(
    tmp_path, row: int, key: int, holder: str
):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, row)
    _press(menu, key)
    key_name = pygame.key.name(key).upper()
    assert menu.lines()[5] == f"{key_name} is already used by {holder}"


def test_rejected_key_leaves_every_binding_unchanged(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    before = dict(menu.settings.bindings)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_UP)  # Player 2 up's key
    assert menu.settings.bindings == before


def test_rejection_ends_the_wait_so_a_later_key_is_not_bound(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_s)  # rejected
    assert not menu.capturing
    _press(menu, pygame.K_i)  # no wait, so this is not bound
    assert menu.settings.bindings["p1_up"] == "w"


def test_a_rejected_message_is_cleared_when_a_row_is_selected_again(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_s)
    assert menu.lines()[5] != ""
    menu.handle(ENTER)  # Player 1 up again, waiting
    assert menu.lines()[5] == ""


def test_rebinding_an_action_to_its_own_key_is_accepted_and_saved(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_w)
    assert menu.lines()[0] == "Player 1 up: W"
    assert menu.lines()[5] == ""
    assert load_settings(_config_file(tmp_path)).bindings["p1_up"] == "w"


def test_rejected_key_for_a_new_binding_matches_find_binding_conflicts(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 3)
    candidate = dict(menu.settings.bindings, p2_down="w")
    assert find_binding_conflicts(candidate) == ["p1_up", "p2_down"]
    _press(menu, pygame.K_w)
    assert menu.settings.bindings["p2_down"] == "down"


# A valid key: save and apply


def test_valid_key_is_saved_to_the_config_file(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_i)
    saved = json.loads(_config_file(tmp_path).read_text(encoding="utf-8"))
    assert saved["bindings"] == {
        "p1_up": "i",
        "p1_down": "s",
        "p2_up": "up",
        "p2_down": "down",
    }


def test_binding_is_restored_on_relaunch(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_i)

    relaunched = MainMenu(load_settings(_config_file(tmp_path)), _config_file(tmp_path))
    assert relaunched.settings.bindings["p1_up"] == "i"


def test_failed_save_still_applies_the_binding_for_this_session(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("in the way")
    path = blocker / "config.json"
    assert save_settings(path, default_settings()) is False

    menu = MainMenu(default_settings(), path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_i)
    assert menu.settings.bindings["p1_up"] == "i"
    assert menu.lines()[0] == "Player 1 up: I"


def test_new_binding_takes_effect_on_the_next_frame(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_i)
    _back_to_main(menu)

    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    ai = AIController(Difficulty.MEDIUM, random.Random(0))
    # The old key no longer moves Player 1.
    p1, _ = main_module._read_directions(
        _Keys(pygame.K_w), menu.settings, match, ai, 1 / 60
    )
    assert p1 == 0
    # The new key moves Player 1 up on the very next frame.
    p1, _ = main_module._read_directions(
        _Keys(pygame.K_i), menu.settings, match, ai, 1 / 60
    )
    assert p1 == -1


def test_new_binding_applies_to_the_serve_start_key_check(tmp_path):
    menu = _menu(tmp_path)
    _open_controls(menu)
    _wait_for_row(menu, 0)
    _press(menu, pygame.K_i)
    _back_to_main(menu)

    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    # I is now a paddle key, so pressing it does not start the rally.
    main_module._handle_key_down(pygame.K_i, menu.settings, match)
    assert match.serving
    # W is no longer a paddle key, so pressing it starts the rally.
    main_module._handle_key_down(pygame.K_w, menu.settings, match)
    assert not match.serving


def _back_to_main(menu: MainMenu) -> None:
    _select_row(menu, 4)
    menu.handle(ENTER)
    assert menu.page is MenuPage.MAIN


# Drawing


def test_draw_controls_paints_the_highlighted_row_white(tmp_path):
    surface = pygame.Surface((1000, 600))
    menu = _menu(tmp_path)
    _open_controls(menu)
    main_module.draw_menu(surface, menu)
    assert _has_white_in_band(surface, 40, 80)
    assert not _has_white_in_band(surface, 96, 136)

    menu.handle(DOWN)
    main_module.draw_menu(surface, menu)
    assert not _has_white_in_band(surface, 40, 80)
    assert _has_white_in_band(surface, 96, 136)


def _has_white_in_band(surface: pygame.Surface, top: float, bottom: float) -> bool:
    for y in range(int(top), int(bottom)):
        for x in range(surface.get_width()):
            if tuple(surface.get_at((x, y)))[:3] == (255, 255, 255):
                return True
    return False


# The real loop, driven by scripted events


def test_main_loop_rebinds_a_key_then_leaves_with_esc(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_DOWN)],
            [_key(pygame.K_DOWN)],
            [_key(pygame.K_DOWN)],  # Controls
            [_key(pygame.K_RETURN)],  # open Controls
            [_key(pygame.K_RETURN)],  # wait on Player 1 up
            [_key(pygame.K_i)],  # bind it
            [_key(pygame.K_ESCAPE)],  # leave Controls
            [_key(pygame.K_ESCAPE)],  # Esc on the main menu does nothing
        ],
    )
    assert main_module.main() == 0
    assert load_settings(_config_file(tmp_path)).bindings["p1_up"] == "i"


def test_main_loop_rejected_key_on_controls_does_not_start_a_match(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    started: list[Settings] = []
    real_start = main_module._start_match

    def record_start(settings: Settings):
        started.append(settings)
        return real_start(settings)

    monkeypatch.setattr(main_module, "_start_match", record_start)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_DOWN)],
            [_key(pygame.K_DOWN)],
            [_key(pygame.K_DOWN)],  # Controls
            [_key(pygame.K_RETURN)],  # open Controls
            [_key(pygame.K_RETURN)],  # wait on Player 1 up
            [_key(pygame.K_s)],  # rejected, used by Player 1 down
            [_key(pygame.K_ESCAPE)],  # leave Controls
        ],
    )
    assert main_module.main() == 0
    assert started == []
    assert not _config_file(tmp_path).exists()
