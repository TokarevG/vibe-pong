import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.__main__ import (
    PAUSE_ITEMS,
    PauseItem,
    PauseMenu,
    PauseOutcome,
)
from pong.ai import Difficulty
from pong.game import WINNING_SCORE, Match, Mode, Player
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH
from pong.settings import default_settings

pygame = main_module.pygame

DOWN = main_module.MenuAction.DOWN
UP = main_module.MenuAction.UP
ENTER = main_module.MenuAction.ENTER
BACK = main_module.MenuAction.BACK


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


def _highlight(menu: PauseMenu, item: PauseItem) -> None:
    while menu.selected is not item:
        menu.handle(DOWN)


def _surface() -> pygame.Surface:
    return pygame.Surface((PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT))


# The pause menu's state and keys


def test_items_are_resume_restart_main_menu_in_order():
    assert list(PAUSE_ITEMS) == [
        PauseItem.RESUME,
        PauseItem.RESTART,
        PauseItem.MAIN_MENU,
    ]
    assert PauseMenu().lines() == ["Resume", "Restart Match", "Main Menu"]


def test_highlight_starts_on_resume():
    assert PauseMenu().selected is PauseItem.RESUME


def test_down_moves_highlight_and_wraps_from_last_to_first():
    menu = PauseMenu()
    assert menu.handle(DOWN) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESTART
    assert menu.handle(DOWN) is PauseOutcome.NONE
    assert menu.selected is PauseItem.MAIN_MENU
    assert menu.handle(DOWN) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESUME


def test_up_wraps_from_first_to_last_and_back():
    menu = PauseMenu()
    assert menu.handle(UP) is PauseOutcome.NONE
    assert menu.selected is PauseItem.MAIN_MENU
    assert menu.handle(UP) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESTART
    assert menu.handle(UP) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESUME


def test_moving_the_highlight_does_not_activate_the_row():
    menu = PauseMenu()
    assert menu.handle(DOWN) is PauseOutcome.NONE
    assert menu.handle(UP) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESUME


@pytest.mark.parametrize(
    ("item", "outcome"),
    [
        (PauseItem.RESUME, PauseOutcome.RESUME),
        (PauseItem.RESTART, PauseOutcome.RESTART),
        (PauseItem.MAIN_MENU, PauseOutcome.MAIN_MENU),
    ],
)
def test_enter_activates_the_highlighted_row(item: PauseItem, outcome: PauseOutcome):
    menu = PauseMenu()
    _highlight(menu, item)
    assert menu.handle(ENTER) is outcome


@pytest.mark.parametrize("item", list(PAUSE_ITEMS))
def test_esc_resumes_whatever_is_highlighted(item: PauseItem):
    menu = PauseMenu()
    _highlight(menu, item)
    assert main_module._handle_pause_key(pygame.K_ESCAPE, menu) is (PauseOutcome.RESUME)


def test_arrow_and_enter_keys_drive_the_pause_menu():
    menu = PauseMenu()
    assert main_module._handle_pause_key(pygame.K_DOWN, menu) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESTART
    assert main_module._handle_pause_key(pygame.K_UP, menu) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESUME
    assert main_module._handle_pause_key(pygame.K_RETURN, menu) is (PauseOutcome.RESUME)


@pytest.mark.parametrize("key", [pygame.K_w, pygame.K_s, pygame.K_SPACE])
def test_non_navigation_keys_do_nothing_in_the_pause_menu(key: int):
    menu = PauseMenu()
    assert main_module._handle_pause_key(key, menu) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESUME


def test_navigation_keys_ignore_the_paddle_bindings():
    # Rebind P1 to W and S. The pause menu still answers to the arrows and Enter,
    # and W and S do nothing in it.
    settings = default_settings()
    settings.bindings["p1_up"] = "w"
    settings.bindings["p1_down"] = "s"
    menu = PauseMenu()
    assert main_module._handle_pause_key(pygame.K_w, menu) is PauseOutcome.NONE
    assert main_module._handle_pause_key(pygame.K_s, menu) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESUME
    assert main_module._handle_pause_key(pygame.K_DOWN, menu) is PauseOutcome.NONE
    assert menu.selected is PauseItem.RESTART


# The pause menu drawn over the playfield


def test_draw_pause_menu_keeps_the_playfield_visible():
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    surface = _surface()
    main_module.draw_frame(surface, match)
    # The middle of P1's paddle is white in the frame. The shade dims it but does
    # not hide it.
    paddle_x = round(match.p1.x + match.p1.width / 2)
    paddle_y = round(match.p1.y + match.p1.height / 2)
    assert tuple(surface.get_at((paddle_x, paddle_y)))[:3] == (255, 255, 255)

    main_module.draw_pause_menu(surface, PauseMenu())

    shaded = tuple(surface.get_at((paddle_x, paddle_y)))[:3]
    assert shaded != (255, 255, 255)
    assert sum(shaded) > 0


def test_draw_pause_menu_highlight_changes_the_drawing():
    resume_first = _surface()
    main_module.draw_pause_menu(resume_first, PauseMenu())

    main_menu_first = _surface()
    menu = PauseMenu()
    _highlight(menu, PauseItem.MAIN_MENU)
    main_module.draw_pause_menu(main_menu_first, menu)

    assert pygame.image.tobytes(resume_first, "RGB") != pygame.image.tobytes(
        main_menu_first, "RGB"
    )


def test_draw_pause_menu_does_nothing_for_zero_size():
    surface = pygame.Surface((0, 0))
    main_module.draw_pause_menu(surface, PauseMenu())
    assert surface.get_size() == (0, 0)


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


class _Frame:
    """What one loop frame drew, and the state of the match at that point."""

    def __init__(self, screen: str, paused: bool, p1_y: float, ball: tuple[float, ...]):
        self.screen = screen  # "menu", "play" or "pause"
        self.paused = paused
        self.p1_y = p1_y
        self.ball = ball


class _Recorder:
    def __init__(self) -> None:
        self.matches: list[Match] = []
        self.ais: list[object] = []
        self.frames: list[_Frame] = []


def _record(monkeypatch) -> _Recorder:
    """Wrap the loop's drawing and match creation so a test can see each frame."""
    rec = _Recorder()
    real_start = main_module._start_match

    def record_start(settings):
        match, ai = real_start(settings)
        rec.matches.append(match)
        rec.ais.append(ai)
        return match, ai

    real_draw_frame = main_module.draw_frame
    real_draw_pause = main_module.draw_pause_menu
    real_draw_menu = main_module.draw_menu

    def snapshot(screen: str, match: Match) -> _Frame:
        return _Frame(screen, match.paused, match.p1.y, (match.ball.x, match.ball.y))

    def record_frame(surface, match):
        real_draw_frame(surface, match)
        rec.frames.append(snapshot("play", match))

    def record_pause(surface, pause):
        real_draw_pause(surface, pause)
        # The pause menu is drawn after the playfield in the same frame, so it
        # replaces that frame's "play" entry.
        rec.frames[-1] = snapshot("pause", rec.matches[-1])

    def record_menu(surface, menu):
        real_draw_menu(surface, menu)
        rec.frames.append(_Frame("menu", False, 0.0, (0.0, 0.0)))

    monkeypatch.setattr(main_module, "_start_match", record_start)
    monkeypatch.setattr(main_module, "draw_frame", record_frame)
    monkeypatch.setattr(main_module, "draw_pause_menu", record_pause)
    monkeypatch.setattr(main_module, "draw_menu", record_menu)
    return rec


@pytest.fixture
def config_home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def test_esc_during_a_match_pauses_and_shows_the_pause_menu(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(monkeypatch, [[_key(pygame.K_RETURN)], [_key(pygame.K_ESCAPE)], []])
    assert main_module.main() == 0
    assert rec.matches[0].paused
    last = rec.frames[-1]
    assert last.screen == "pause"
    assert last.paused


def test_esc_while_paused_resumes_the_match(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [[_key(pygame.K_RETURN)], [_key(pygame.K_ESCAPE)], [_key(pygame.K_ESCAPE)], []],
    )
    assert main_module.main() == 0
    assert not rec.matches[0].paused
    assert rec.frames[-1].screen == "play"


def test_resume_row_unpauses_and_closes_the_menu(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],
            [_key(pygame.K_ESCAPE)],
            [_key(pygame.K_RETURN)],  # Resume is highlighted
            [],
        ],
    )
    assert main_module.main() == 0
    assert not rec.matches[0].paused
    assert rec.frames[-1].screen == "play"


def test_paused_frames_keep_the_ball_where_the_pause_began(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],
            [_key(pygame.K_SPACE)],  # serve, so the ball is moving
            [_key(pygame.K_ESCAPE)],
            [],
            [],
            [],
        ],
    )
    assert main_module.main() == 0
    paused = [f for f in rec.frames if f.screen == "pause"]
    assert len(paused) >= 3
    assert len({f.ball for f in paused}) == 1
    # The serve set the ball moving before the pause, so the pause froze a ball
    # in motion.
    assert rec.matches[0].ball.vx != 0.0


def test_paddle_keys_do_not_move_paddles_while_paused(config_home, monkeypatch):
    class _Held:
        def __getitem__(self, key_code):
            return key_code == pygame.K_w

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Held())
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],
            [_key(pygame.K_ESCAPE)],
            [],
            [],
            [],
        ],
    )
    assert main_module.main() == 0
    paused = [f for f in rec.frames if f.screen == "pause"]
    assert len(paused) >= 3
    # W is held the whole time, but P1 does not move while the menu is open.
    assert len({f.p1_y for f in paused}) == 1


def test_key_presses_do_not_start_a_rally_while_paused(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game
            [_key(pygame.K_ESCAPE)],  # pause before the serve
            [_key(pygame.K_SPACE)],  # would start the serve if not paused
            [],
        ],
    )
    assert main_module.main() == 0
    assert rec.matches[0].serving
    assert rec.matches[0].paused


def test_restart_row_resets_the_match_and_closes_the_menu(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game
            [_key(pygame.K_SPACE)],  # serve
            [_key(pygame.K_ESCAPE)],  # pause
            [_key(pygame.K_DOWN)],  # highlight Restart Match
            [_key(pygame.K_RETURN)],  # restart
            [],
        ],
    )
    assert main_module.main() == 0
    match = rec.matches[0]
    assert not match.paused
    assert match.serving
    assert match.score.points(Player.P1) == 0
    assert match.score.points(Player.P2) == 0
    assert rec.frames[-1].screen == "play"
    assert not rec.frames[-1].paused


def test_restart_row_makes_a_new_ai_controller(config_home, monkeypatch):
    restarted: list[object] = []
    real_restart = main_module._restart_match

    def record_restart(match, settings):
        ai = real_restart(match, settings)
        restarted.append(ai)
        return ai

    monkeypatch.setattr(main_module, "_restart_match", record_restart)
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game
            [_key(pygame.K_ESCAPE)],  # pause
            [_key(pygame.K_DOWN)],  # Restart Match
            [_key(pygame.K_RETURN)],  # restart
            [],
        ],
    )
    assert main_module.main() == 0
    assert len(rec.ais) == 1
    assert len(restarted) == 1
    # Restart replaces the controller, so its reaction timers start over.
    assert restarted[0] is not rec.ais[0]


def test_restart_match_helper_resets_the_match_and_returns_a_new_ai():
    settings = default_settings()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    match.start_rally()
    for _ in range(3):
        match.end_rally(Player.P2)
    match.toggle_pause()
    old_ai = main_module._start_match(settings)[1]

    ai = main_module._restart_match(match, settings)

    assert ai is not old_ai
    assert match.serving
    assert not match.paused
    assert match.score.points(Player.P2) == 0


def test_main_menu_row_discards_the_match_and_shows_the_main_menu(
    config_home, monkeypatch
):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game
            [_key(pygame.K_ESCAPE)],  # pause
            [_key(pygame.K_UP)],  # wraps to Main Menu
            [_key(pygame.K_RETURN)],  # Main Menu
            [],
        ],
    )
    assert main_module.main() == 0
    # Frames: start, Esc, Up, Enter on Main Menu, then the idle frame and the QUIT frame.
    assert [f.screen for f in rec.frames] == [
        "play",
        "pause",
        "pause",
        "menu",
        "menu",
        "menu",
    ]


def test_after_main_menu_a_new_match_starts_unpaused(config_home, monkeypatch):
    rec = _record(monkeypatch)
    _script_events(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game
            [_key(pygame.K_ESCAPE)],  # pause
            [_key(pygame.K_UP)],
            [_key(pygame.K_RETURN)],  # Main Menu
            [_key(pygame.K_RETURN)],  # Start Game again
            [],
        ],
    )
    assert main_module.main() == 0
    assert len(rec.matches) == 2
    assert not rec.matches[1].paused
    assert rec.frames[-1].screen == "play"


def test_esc_after_a_win_does_not_open_the_pause_menu(config_home, monkeypatch):
    real_start = main_module._start_match
    matches: list[Match] = []

    def start_and_win(settings):
        match, ai = real_start(settings)
        for _ in range(WINNING_SCORE):
            match.score.award(Player.P1)
        matches.append(match)
        return match, ai

    monkeypatch.setattr(main_module, "_start_match", start_and_win)
    rec = _record(monkeypatch)
    _script_events(monkeypatch, [[_key(pygame.K_RETURN)], [_key(pygame.K_ESCAPE)], []])
    assert main_module.main() == 0
    assert matches[0].score.winner() is Player.P1
    assert not matches[0].paused
    assert all(f.screen != "pause" for f in rec.frames)
