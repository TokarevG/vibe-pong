import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.ai import AIController, Difficulty
from pong.game import Match, Mode
from pong.settings import Settings, default_settings

pygame = main_module.pygame


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def fresh_font_cache():
    # main() quits pygame when it returns, which leaves fonts cached by
    # _digit_font unusable for the next test module.
    yield
    main_module._digit_font.cache_clear()


class _Keys:
    """Stands in for ``pygame.key.get_pressed()`` with the given key codes held."""

    def __init__(self, *held: int) -> None:
        self._held = set(held)

    def __getitem__(self, key_code: int) -> bool:
        return key_code in self._held


class _StubAI(AIController):
    """An AI controller that always returns ``answer`` and records its calls."""

    def __init__(self, answer: int) -> None:
        super().__init__(Difficulty.MEDIUM, random.Random(0))
        self.answer = answer
        self.calls: list[tuple[float, float, float]] = []

    def update(self, dt: float, ball_y: float, paddle_center_y: float) -> int:
        self.calls.append((dt, ball_y, paddle_center_y))
        return self.answer


FRAME = 1 / 60


def _run(match: Match, settings: Settings, held: _Keys, frames: int, dt: float = FRAME):
    """Run ``frames`` frames of key reading and match updates, as the game loop does."""
    ai = _StubAI(0)
    for _ in range(frames):
        p1, p2 = main_module._read_directions(held, settings, match, ai, dt)
        match.update(dt, p1, p2)


def test_direction_is_minus_one_for_up_only_and_plus_one_for_down_only():
    assert main_module._direction(True, False) == -1
    assert main_module._direction(False, True) == 1


@pytest.mark.parametrize("up, down", [(False, False), (True, True)])
def test_direction_is_zero_when_neither_or_both_pressed(up: bool, down: bool):
    assert main_module._direction(up, down) == 0


def test_stored_key_names_map_to_pygame_key_codes():
    assert main_module._key_code("w", "p1_up") == pygame.K_w
    assert main_module._key_code("up", "p2_up") == pygame.K_UP
    assert main_module._key_code("down", "p2_down") == pygame.K_DOWN
    assert main_module._key_code("escape", "p1_up") == pygame.K_ESCAPE


def test_unknown_key_name_falls_back_to_the_default_key_for_the_action():
    assert main_module._key_code("nosuchkey", "p1_up") == pygame.K_w
    assert main_module._key_code("nosuchkey", "p2_down") == pygame.K_DOWN


def test_held_keys_are_checked_against_the_bound_key_codes():
    settings = default_settings()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    ai = _StubAI(0)

    held = _Keys(pygame.K_w)
    assert main_module._read_directions(held, settings, match, ai, FRAME) == (-1, 0)
    held = _Keys(pygame.K_s)
    assert main_module._read_directions(held, settings, match, ai, FRAME) == (1, 0)


def test_two_player_p2_direction_comes_from_p2_keys():
    settings = default_settings()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    ai = _StubAI(1)

    up = _Keys(pygame.K_UP)
    assert main_module._read_directions(up, settings, match, ai, FRAME) == (0, -1)
    down = _Keys(pygame.K_DOWN)
    assert main_module._read_directions(down, settings, match, ai, FRAME) == (0, 1)
    assert ai.calls == []


def test_single_player_p2_direction_comes_from_the_ai_and_p2_keys_are_ignored():
    settings = default_settings()
    match = Match(Mode.SINGLE_PLAYER, Difficulty.MEDIUM)
    ai = _StubAI(1)

    held = _Keys(pygame.K_UP)
    p1, p2 = main_module._read_directions(held, settings, match, ai, FRAME)
    assert p2 == 1
    assert p1 == 0

    ai.answer = -1
    held = _Keys(pygame.K_DOWN)
    _, p2 = main_module._read_directions(held, settings, match, ai, FRAME)
    assert p2 == -1


def test_single_player_ai_is_given_dt_ball_y_and_paddle_centre():
    settings = default_settings()
    match = Match(Mode.SINGLE_PLAYER, Difficulty.MEDIUM)
    ai = _StubAI(0)

    main_module._read_directions(_Keys(), settings, match, ai, 0.25)

    dt, ball_y, paddle_centre_y = ai.calls[0]
    assert dt == 0.25
    assert ball_y == match.ball.y
    assert paddle_centre_y == match.p2.y + match.p2.height / 2


def test_rebinding_takes_effect_on_the_next_frame():
    settings = default_settings()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    ai = _StubAI(0)

    settings.bindings["p1_up"] = "i"
    assert main_module._read_directions(
        _Keys(pygame.K_i), settings, match, ai, FRAME
    ) == (-1, 0)
    assert main_module._read_directions(
        _Keys(pygame.K_w), settings, match, ai, FRAME
    ) == (0, 0)


def test_paddle_moves_at_420_px_per_second_at_any_frame_rate():
    for dt in (1 / 50, 1 / 60, 1 / 100):
        match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
        start = match.p1.y
        _run(match, default_settings(), _Keys(pygame.K_s), round(0.5 / dt), dt=dt)
        assert match.p1.y - start == pytest.approx(210.0, abs=1e-6)


def test_paddle_stops_in_the_frame_after_the_key_is_released():
    settings = default_settings()
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    _run(match, settings, _Keys(pygame.K_s), 5)
    y_before_release = match.p1.y

    _run(match, settings, _Keys(), 1)
    assert match.p1.y == y_before_release
    assert match.p1.velocity == 0.0


def test_holding_both_keys_does_not_move_the_paddle():
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    start = match.p1.y
    _run(match, default_settings(), _Keys(pygame.K_w, pygame.K_s), 30)
    assert match.p1.y == start


def test_held_keys_do_not_move_the_paddle_while_paused():
    match = Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)
    match.toggle_pause()
    start = match.p1.y
    _run(match, default_settings(), _Keys(pygame.K_s), 10)
    assert match.p1.y == start


def test_main_reads_key_state_once_per_frame_and_loads_settings_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    frames = 3
    events_calls = 0

    def fake_events() -> list[pygame.event.Event]:
        nonlocal events_calls
        events_calls += 1
        if events_calls == 1:
            # The game opens on the main menu. Enter on Start Game begins a match.
            return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        if events_calls == frames:
            return [pygame.event.Event(pygame.QUIT)]
        return []

    reads = 0

    def fake_get_pressed() -> _Keys:
        nonlocal reads
        reads += 1
        return _Keys()

    loads = 0
    real_load = main_module.load_settings

    def counting_load(path: Path) -> Settings:
        nonlocal loads
        loads += 1
        return real_load(path)

    monkeypatch.setattr(pygame.event, "get", fake_events)
    monkeypatch.setattr(pygame.key, "get_pressed", fake_get_pressed)
    monkeypatch.setattr(main_module, "load_settings", counting_load)

    assert main_module.main() == 0
    assert reads == frames
    assert loads == 1
