import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.__main__ import (
    AUDIO_ITEMS,
    AudioItem,
    AudioScreen,
    MainMenu,
    MenuAction,
    MenuItem,
    MenuOutcome,
    MenuPage,
)
from pong.settings import Settings, default_settings, load_settings, save_settings

pygame = main_module.pygame

DOWN = MenuAction.DOWN
UP = MenuAction.UP
LEFT = MenuAction.LEFT
RIGHT = MenuAction.RIGHT
ENTER = MenuAction.ENTER
BACK = MenuAction.BACK


@pytest.fixture(autouse=True)
def pygame_session():
    pygame.init()
    main_module._menu_font.cache_clear()
    yield
    main_module._menu_font.cache_clear()
    pygame.quit()


def _config(tmp_path: Path) -> Path:
    return tmp_path / "pong" / "config.json"


def _menu(tmp_path: Path, settings: Settings | None = None) -> MainMenu:
    return MainMenu(settings or default_settings(), _config(tmp_path))


def _open_audio(menu: MainMenu) -> None:
    """Move the main menu highlight to Audio and press Enter."""
    while menu.selected is not MenuItem.AUDIO:
        menu.handle(DOWN)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.page is MenuPage.AUDIO


def _audio(tmp_path: Path, settings: Settings | None = None) -> AudioScreen:
    return AudioScreen(settings or default_settings(), _config(tmp_path))


def _saved(tmp_path: Path) -> Settings:
    return load_settings(_config(tmp_path))


def _has_white_in_band(surface: pygame.Surface, top: float, bottom: float) -> bool:
    for y in range(int(top), int(bottom)):
        for x in range(surface.get_width()):
            if tuple(surface.get_at((x, y)))[:3] == (255, 255, 255):
                return True
    return False


def _lit_pixels(surface: pygame.Surface) -> int:
    black = pygame.mask.from_threshold(surface, (0, 0, 0, 255), (1, 1, 1, 255))
    return surface.get_width() * surface.get_height() - black.count()


def _key(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _script_events(monkeypatch, frames: list[list[pygame.event.Event]]) -> None:
    queue = list(frames)

    def fake_get(*args, **kwargs):
        if queue:
            return queue.pop(0)
        return [pygame.event.Event(pygame.QUIT)]

    monkeypatch.setattr(pygame.event, "get", fake_get)


# Opening the screen and the rows


def test_audio_opens_from_main_menu_with_sound_volume_and_back(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    assert menu.lines() == ["Sound: On", "Volume: 80", "Back"]
    assert menu.highlighted_line == 0


def test_audio_rows_are_sound_volume_back_in_order():
    assert list(AUDIO_ITEMS) == [AudioItem.SOUND, AudioItem.VOLUME, AudioItem.BACK]


def test_audio_screen_shows_off_when_sound_is_off(tmp_path):
    settings = default_settings()
    settings.audio_enabled = False
    assert _audio(tmp_path, settings).lines()[0] == "Sound: Off"


def test_down_and_up_move_the_highlight_and_wrap_over_three_rows(tmp_path):
    screen = _audio(tmp_path)
    assert screen.selected is AudioItem.SOUND
    screen.handle(DOWN)
    assert screen.selected is AudioItem.VOLUME
    screen.handle(DOWN)
    assert screen.selected is AudioItem.BACK
    assert screen.handle(DOWN) is False
    assert screen.selected is AudioItem.SOUND
    assert screen.handle(UP) is False
    assert screen.selected is AudioItem.BACK


def test_moving_the_highlight_changes_nothing_and_saves_nothing(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(DOWN)
    menu.handle(UP)
    assert menu.settings == default_settings()
    assert not _config(tmp_path).exists()


# Sound


def test_enter_on_sound_turns_it_off_then_on(tmp_path):
    screen = _audio(tmp_path)
    assert screen.handle(ENTER) is False
    assert screen.settings.audio_enabled is False
    assert screen.lines()[0] == "Sound: Off"
    assert screen.handle(ENTER) is False
    assert screen.settings.audio_enabled is True
    assert screen.lines()[0] == "Sound: On"


def test_sound_toggle_is_saved_immediately(tmp_path):
    screen = _audio(tmp_path)
    screen.handle(ENTER)
    assert _saved(tmp_path).audio_enabled is False
    screen.handle(ENTER)
    assert _saved(tmp_path).audio_enabled is True


@pytest.mark.parametrize("key_action", [LEFT, RIGHT])
def test_left_and_right_on_sound_do_nothing(tmp_path, key_action: MenuAction):
    screen = _audio(tmp_path)
    assert screen.handle(key_action) is False
    assert screen.settings == default_settings()
    assert not _config(tmp_path).exists()


# Volume


def test_right_raises_volume_by_ten_and_left_lowers_it(tmp_path):
    screen = _audio(tmp_path)
    screen.handle(DOWN)
    screen.handle(RIGHT)
    assert screen.settings.volume == 90
    assert screen.lines()[1] == "Volume: 90"
    screen.handle(LEFT)
    screen.handle(LEFT)
    assert screen.settings.volume == 70
    assert screen.lines()[1] == "Volume: 70"


def test_volume_change_is_saved_immediately(tmp_path):
    screen = _audio(tmp_path)
    screen.handle(DOWN)
    screen.handle(RIGHT)
    assert _saved(tmp_path).volume == 90


def test_volume_stops_at_100(tmp_path):
    screen = _audio(tmp_path, _with_volume(100))
    screen.handle(DOWN)
    screen.handle(RIGHT)
    assert screen.settings.volume == 100
    assert screen.lines()[1] == "Volume: 100"


def test_volume_stops_at_0(tmp_path):
    screen = _audio(tmp_path, _with_volume(0))
    screen.handle(DOWN)
    screen.handle(LEFT)
    assert screen.settings.volume == 0
    assert screen.lines()[1] == "Volume: 0"


def test_steps_reach_both_ends_from_the_default(tmp_path):
    screen = _audio(tmp_path)
    screen.handle(DOWN)
    for _ in range(20):
        screen.handle(RIGHT)
    assert screen.settings.volume == 100
    for _ in range(20):
        screen.handle(LEFT)
    assert screen.settings.volume == 0


def test_a_volume_that_is_not_a_multiple_of_ten_clamps_at_the_ends(tmp_path):
    screen = _audio(tmp_path, _with_volume(95))
    screen.handle(DOWN)
    screen.handle(RIGHT)
    assert screen.settings.volume == 100
    screen = _audio(tmp_path, _with_volume(5))
    screen.handle(DOWN)
    screen.handle(LEFT)
    assert screen.settings.volume == 0


def test_no_save_when_volume_is_already_at_the_limit(tmp_path):
    screen = _audio(tmp_path, _with_volume(0))
    screen.handle(DOWN)
    screen.handle(LEFT)
    assert not _config(tmp_path).exists()


def test_volume_can_change_while_sound_is_off(tmp_path):
    screen = _audio(tmp_path)
    screen.handle(ENTER)  # Sound off
    screen.handle(DOWN)
    screen.handle(LEFT)
    assert screen.settings.audio_enabled is False
    assert screen.settings.volume == 70
    saved = _saved(tmp_path)
    assert saved.audio_enabled is False
    assert saved.volume == 70


def test_enter_on_volume_does_nothing(tmp_path):
    screen = _audio(tmp_path)
    screen.handle(DOWN)
    assert screen.handle(ENTER) is False
    assert screen.settings == default_settings()
    assert not _config(tmp_path).exists()


def _with_volume(volume: int) -> Settings:
    settings = default_settings()
    settings.volume = volume
    return settings


# Closing the screen


def test_enter_on_back_returns_to_the_main_menu_with_audio_highlighted(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(DOWN)
    menu.handle(DOWN)
    assert menu.handle(ENTER) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN
    assert menu.selected is MenuItem.AUDIO


def test_back_action_returns_to_the_main_menu(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    assert menu.handle(BACK) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN


def test_esc_returns_to_the_main_menu_from_any_row(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(DOWN)
    assert main_module._handle_menu_key(pygame.K_ESCAPE, menu) is MenuOutcome.NONE
    assert menu.page is MenuPage.MAIN


def test_left_and_right_keys_reach_the_audio_screen(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(DOWN)
    main_module._handle_menu_key(pygame.K_LEFT, menu)
    assert menu.settings.volume == 70
    main_module._handle_menu_key(pygame.K_RIGHT, menu)
    assert menu.settings.volume == 80


def test_left_and_right_keys_do_nothing_on_the_main_menu(tmp_path):
    menu = _menu(tmp_path)
    assert main_module._handle_menu_key(pygame.K_LEFT, menu) is MenuOutcome.NONE
    assert main_module._handle_menu_key(pygame.K_RIGHT, menu) is MenuOutcome.NONE
    assert menu.selected is MenuItem.START_GAME
    assert menu.settings == default_settings()


# Saving and restoring


def test_failed_save_still_applies_both_values_for_this_session(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("in the way")
    path = blocker / "config.json"
    assert save_settings(path, default_settings()) is False

    menu = MainMenu(default_settings(), path)
    _open_audio(menu)
    menu.handle(ENTER)
    assert menu.settings.audio_enabled is False
    menu.handle(DOWN)
    menu.handle(LEFT)
    assert menu.settings.volume == 70
    assert menu.lines()[:2] == ["Sound: Off", "Volume: 70"]


def test_restart_shows_and_uses_the_saved_values(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(ENTER)  # Sound off
    menu.handle(DOWN)
    menu.handle(LEFT)  # 70
    menu.handle(LEFT)  # 60

    relaunched = MainMenu(load_settings(_config(tmp_path)), _config(tmp_path))
    assert relaunched.settings.audio_enabled is False
    assert relaunched.settings.volume == 60
    _open_audio(relaunched)
    assert relaunched.lines() == ["Sound: Off", "Volume: 60", "Back"]


def test_saved_file_holds_the_audio_values(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(ENTER)
    menu.handle(DOWN)
    menu.handle(RIGHT)
    data = json.loads(_config(tmp_path).read_text(encoding="utf-8"))
    assert data["audio_enabled"] is False
    assert data["volume"] == 90


# Drawing


def test_draw_menu_draws_the_audio_screen(tmp_path):
    surface = pygame.Surface((1000, 600))
    menu = _menu(tmp_path)
    _open_audio(menu)
    main_module.draw_menu(surface, menu)
    assert _lit_pixels(surface) > 0
    # The Sound row is highlighted first, centred at logical y 60.
    assert _has_white_in_band(surface, 40, 80)
    assert not _has_white_in_band(surface, 96, 136)


def test_draw_menu_highlights_the_volume_row_when_selected(tmp_path):
    menu = _menu(tmp_path)
    _open_audio(menu)
    menu.handle(DOWN)
    surface = pygame.Surface((1000, 600))
    main_module.draw_menu(surface, menu)
    # Row 1 of the screen is centred at logical y 116, which is pixel y 116 here.
    assert _has_white_in_band(surface, 100, 132)
    assert not _has_white_in_band(surface, 40, 80)


# The real loop, driven by scripted events


def test_main_loop_changes_audio_settings_and_restores_them_on_relaunch(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_DOWN)],  # Mode
            [_key(pygame.K_DOWN)],  # Difficulty
            [_key(pygame.K_DOWN)],  # Controls
            [_key(pygame.K_DOWN)],  # Audio
            [_key(pygame.K_RETURN)],  # open Audio
            [_key(pygame.K_RETURN)],  # Sound off
            [_key(pygame.K_DOWN)],  # Volume
            [_key(pygame.K_LEFT)],  # 70
            [_key(pygame.K_ESCAPE)],  # back to the main menu
            [_key(pygame.K_DOWN)],  # Quit
            [_key(pygame.K_RETURN)],  # quit
        ],
    )
    assert main_module.main() == 0
    saved = load_settings(_config(tmp_path))
    assert saved.audio_enabled is False
    assert saved.volume == 70

    # Relaunch: the loaded values are the starting values of the Audio screen.
    menu = MainMenu(load_settings(_config(tmp_path)), _config(tmp_path))
    _open_audio(menu)
    assert menu.lines() == ["Sound: Off", "Volume: 70", "Back"]
