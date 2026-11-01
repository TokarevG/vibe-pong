import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.ai import Difficulty
from pong.game import Match, Mode, Player
from pong.physics import SERVE_SPEED
from pong.settings import Settings, default_settings

pygame = main_module.pygame


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def fresh_font_cache():
    # main() quits pygame when it returns, which leaves cached fonts unusable.
    yield
    main_module._digit_font.cache_clear()


def _match(mode: Mode = Mode.TWO_PLAYER) -> Match:
    return Match(mode, Difficulty.MEDIUM)


def _press(key: int, settings: Settings, match: Match) -> None:
    main_module._handle_key_down(key, settings, match)


def test_non_paddle_key_starts_the_serve():
    match = _match()
    _press(pygame.K_SPACE, default_settings(), match)
    assert not match.serving
    assert match.ball.vx == -SERVE_SPEED


@pytest.mark.parametrize(
    "key", [pygame.K_RETURN, pygame.K_a, pygame.K_LSHIFT, pygame.K_LCTRL]
)
def test_any_other_key_including_lone_modifiers_starts_the_serve(key: int):
    match = _match()
    _press(key, default_settings(), match)
    assert not match.serving


@pytest.mark.parametrize("mode", [Mode.TWO_PLAYER, Mode.SINGLE_PLAYER])
@pytest.mark.parametrize("key", [pygame.K_w, pygame.K_s, pygame.K_UP, pygame.K_DOWN])
def test_paddle_keys_do_not_start_the_serve_in_either_mode(mode: Mode, key: int):
    match = _match(mode)
    _press(key, default_settings(), match)
    assert match.serving
    assert match.ball.vx == 0.0


def test_p2_keys_do_not_start_the_serve_in_single_player():
    match = _match(Mode.SINGLE_PLAYER)
    _press(pygame.K_DOWN, default_settings(), match)
    _press(pygame.K_UP, default_settings(), match)
    assert match.serving


def test_esc_does_not_start_the_serve():
    match = _match()
    _press(pygame.K_ESCAPE, default_settings(), match)
    assert match.serving


def test_key_press_while_rallying_changes_nothing():
    match = _match()
    _press(pygame.K_SPACE, default_settings(), match)
    vx, vy = match.ball.vx, match.ball.vy
    _press(pygame.K_SPACE, default_settings(), match)
    _press(pygame.K_RETURN, default_settings(), match)
    assert (match.ball.vx, match.ball.vy) == (vx, vy)
    assert not match.serving


def test_key_press_while_paused_does_not_start_the_serve():
    match = _match()
    match.toggle_pause()
    _press(pygame.K_SPACE, default_settings(), match)
    assert match.serving
    assert match.ball.vx == 0.0


def test_after_serve_the_ball_moves_and_the_match_is_no_longer_serving():
    match = _match()
    _press(pygame.K_SPACE, default_settings(), match)
    x_before = match.ball.x
    match.update(1 / 60, 0, 0)
    assert match.ball.x != x_before
    assert not match.serving


def test_after_a_point_a_non_paddle_key_serves_toward_the_player_who_conceded():
    match = _match()
    _press(pygame.K_SPACE, default_settings(), match)
    match.end_rally(Player.P1)
    assert match.serving

    _press(pygame.K_SPACE, default_settings(), match)
    assert match.ball.vx == SERVE_SPEED


def test_after_a_point_a_paddle_key_does_not_serve():
    match = _match()
    _press(pygame.K_SPACE, default_settings(), match)
    match.end_rally(Player.P2)
    _press(pygame.K_w, default_settings(), match)
    _press(pygame.K_DOWN, default_settings(), match)
    assert match.serving


def test_rebound_paddle_key_does_not_start_the_serve_and_old_key_does():
    settings = default_settings()
    settings.bindings["p1_up"] = "i"

    match = _match()
    _press(pygame.K_i, settings, match)
    assert match.serving

    _press(pygame.K_w, settings, match)
    assert not match.serving


def test_main_loop_routes_keydown_events_to_the_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    created: list[Match] = []

    class RecordingMatch(Match):
        def __init__(self, mode: Mode, difficulty: Difficulty) -> None:
            super().__init__(mode, difficulty)
            created.append(self)

    frames = 0

    def fake_events() -> list[pygame.event.Event]:
        nonlocal frames
        frames += 1
        if frames == 1:
            return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)]
        if frames == 2:
            return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]
        return [pygame.event.Event(pygame.QUIT)]

    class _NoKeys:
        def __getitem__(self, key_code: int) -> bool:
            return False

    monkeypatch.setattr(main_module, "Match", RecordingMatch)
    monkeypatch.setattr(pygame.event, "get", fake_events)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _NoKeys())

    assert main_module.main() == 0
    assert len(created) == 1
    assert not created[0].serving
