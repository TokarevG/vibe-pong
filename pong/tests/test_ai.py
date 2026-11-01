import ast
import dataclasses
import itertools
import math
import random
from pathlib import Path

import pytest

from pong.ai import AI_SETTINGS, DEAD_ZONE, AIController, AISettings, Difficulty

AI_SOURCE = Path(__file__).parent.parent / "ai.py"


def test_module_does_not_import_pygame():
    tree = ast.parse(AI_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "pygame" for name in imported)


def test_difficulty_has_easy_medium_hard():
    assert {d.name for d in Difficulty} == {"EASY", "MEDIUM", "HARD"}


def test_ai_settings_is_frozen():
    settings = AI_SETTINGS[Difficulty.EASY]
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.max_speed = 1.0  # type: ignore[misc]


def test_ai_settings_has_the_three_fields():
    names = {f.name for f in dataclasses.fields(AISettings)}
    assert names == {"reaction_delay", "max_speed", "aim_error"}


def test_table_has_an_entry_for_every_difficulty():
    assert set(AI_SETTINGS) == set(Difficulty)


@pytest.mark.parametrize(
    ("difficulty", "reaction_delay", "max_speed", "aim_error"),
    [
        (Difficulty.EASY, 0.40, 240, 60),
        (Difficulty.MEDIUM, 0.25, 330, 30),
        (Difficulty.HARD, 0.10, 420, 10),
    ],
)
def test_table_values(difficulty, reaction_delay, max_speed, aim_error):
    assert AI_SETTINGS[difficulty] == AISettings(
        reaction_delay=reaction_delay,
        max_speed=max_speed,
        aim_error=aim_error,
    )


def test_reaction_delay_is_easy_then_medium_then_hard():
    s = AI_SETTINGS
    assert (
        s[Difficulty.EASY].reaction_delay
        > s[Difficulty.MEDIUM].reaction_delay
        > s[Difficulty.HARD].reaction_delay
    )


def test_max_speed_is_easy_then_medium_then_hard():
    s = AI_SETTINGS
    assert (
        s[Difficulty.EASY].max_speed
        < s[Difficulty.MEDIUM].max_speed
        < s[Difficulty.HARD].max_speed
    )


def test_aim_error_is_easy_then_medium_then_hard():
    s = AI_SETTINGS
    assert (
        s[Difficulty.EASY].aim_error
        > s[Difficulty.MEDIUM].aim_error
        > s[Difficulty.HARD].aim_error
    )


class FixedOffsetRandom(random.Random):
    """A random source whose uniform() always returns the given offset."""

    def __init__(self, offset: float) -> None:
        super().__init__(0)
        self.offset = offset
        self.calls: list[tuple[float, float]] = []

    def uniform(self, a: float, b: float) -> float:
        self.calls.append((a, b))
        return self.offset


def use_settings(monkeypatch, difficulty, **changes):
    """Swap one difficulty's tuning for a test, leaving the others alone."""
    settings = dataclasses.replace(AI_SETTINGS[difficulty], **changes)
    monkeypatch.setitem(AI_SETTINGS, difficulty, settings)


def test_controller_exposes_max_speed_from_difficulty():
    for difficulty in Difficulty:
        ctrl = AIController(difficulty, random.Random(0))
        assert ctrl.max_speed == AI_SETTINGS[difficulty].max_speed


def test_dead_zone_is_four_pixels():
    assert DEAD_ZONE == 4


def test_update_returns_only_minus_one_zero_or_one():
    rng = random.Random(1)
    ctrl = AIController(Difficulty.MEDIUM, rng)
    for i in range(200):
        ball_y = (i * 37) % 600
        paddle_y = (i * 53) % 600
        result = ctrl.update(1 / 60, ball_y, paddle_y)
        assert type(result) is int
        assert result in (-1, 0, 1)


def test_first_update_takes_a_look_even_with_zero_dt(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    # Ball is well below the paddle, so the first look must aim down.
    assert ctrl.update(0.0, 300.0, 100.0) == 1


def test_no_new_look_before_reaction_delay(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert ctrl.update(0.0, 100.0, 0.0) == 1  # look 1: aim at 100
    # Ball moves to 0 but the controller still aims at 100 until 0.5 s passes.
    assert ctrl.update(0.25, 0.0, 0.0) == 1
    assert ctrl.update(0.2, 0.0, 0.0) == 1


def test_new_look_once_reaction_delay_has_passed(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    ctrl.update(0.0, 100.0, 0.0)  # look 1: aim at 100
    ctrl.update(0.25, 0.0, 0.0)
    # 0.5 s since look 1 has passed, so this call looks at the ball at 0.
    assert ctrl.update(0.25, 0.0, 0.0) == 0


def test_reaction_delay_counts_from_the_last_look(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    ctrl.update(0.0, 100.0, 0.0)  # look 1 aims at 100
    ctrl.update(0.5, 0.0, 0.0)  # look 2 aims at 0
    # Ball moves back to 100. Only 0.25 s since look 2, so still aiming at 0.
    assert ctrl.update(0.25, 100.0, 0.0) == 0


def test_zero_dt_never_takes_a_new_look(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert ctrl.update(0.0, 100.0, 0.0) == 1  # look 1 aims at 100
    for _ in range(10):
        # Ball jumps to 0 but no time passes, so the target stays at 100.
        assert ctrl.update(0.0, 0.0, 0.0) == 1


def test_between_looks_the_direction_follows_the_paddle(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert ctrl.update(0.0, 100.0, 0.0) == 1  # aim at 100, paddle above
    assert ctrl.update(0.1, 100.0, 90.0) == 1  # still aiming at 100
    assert ctrl.update(0.1, 100.0, 100.0) == 0  # paddle reached the target
    assert ctrl.update(0.1, 100.0, 120.0) == -1  # paddle overshot


def test_each_look_draws_offset_uniformly_over_aim_error(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=10.0)
    rng = FixedOffsetRandom(0.0)
    ctrl = AIController(Difficulty.HARD, rng)
    ctrl.update(0.0, 100.0, 100.0)  # look 1
    ctrl.update(0.5, 100.0, 100.0)  # look 2
    assert rng.calls == [(-10.0, 10.0), (-10.0, 10.0)]


def test_target_is_seen_ball_y_plus_offset(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=10.0)
    # Offset +10: target is 110. Paddle at 105 is 5 px above it, so move down.
    ctrl = AIController(Difficulty.HARD, FixedOffsetRandom(10.0))
    assert ctrl.update(0.0, 100.0, 105.0) == 1
    # Paddle at 107 is only 3 px above the target, inside the dead zone.
    ctrl = AIController(Difficulty.HARD, FixedOffsetRandom(10.0))
    assert ctrl.update(0.0, 100.0, 107.0) == 0
    # Offset -10: target is 90. Paddle at 95 is 5 px below it, so move up.
    ctrl = AIController(Difficulty.HARD, FixedOffsetRandom(-10.0))
    assert ctrl.update(0.0, 100.0, 95.0) == -1


@pytest.mark.parametrize(
    ("paddle_y", "expected"),
    [
        (100 - DEAD_ZONE - 1, 1),  # target more than 4 px below: move down
        (100 - DEAD_ZONE, 0),  # exactly 4 px below: hold
        (100, 0),
        (100 + DEAD_ZONE, 0),  # exactly 4 px above: hold
        (100 + DEAD_ZONE + 1, -1),  # target more than 4 px above: move up
    ],
)
def test_dead_zone_boundaries(monkeypatch, paddle_y, expected):
    use_settings(monkeypatch, Difficulty.HARD, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert ctrl.update(0.0, 100.0, paddle_y) == expected


def simulate(difficulty, seed, frames=600, dt=1 / 60):
    """Run one AI paddle against a fixed ball path and return its mean distance.

    The ball sweeps up and down the field as a sine wave. The paddle moves at the
    controller's max_speed in the direction it returns.
    """
    ball_path = [
        300.0 + 150.0 * math.sin(2 * math.pi * i * dt / 4.0) for i in range(frames)
    ]
    ctrl = AIController(difficulty, random.Random(seed))
    paddle_y = ball_path[0]
    total = 0.0
    for ball_y in ball_path:
        direction = ctrl.update(dt, ball_y, paddle_y)
        assert direction in (-1, 0, 1)
        paddle_y += direction * ctrl.max_speed * dt
        total += abs(paddle_y - ball_y)
    return total / frames


def test_hard_tracks_the_ball_better_than_easy():
    seeds = range(5)
    hard = sum(simulate(Difficulty.HARD, seed) for seed in seeds) / len(seeds)
    easy = sum(simulate(Difficulty.EASY, seed) for seed in seeds) / len(seeds)
    assert hard < easy


def test_simulation_only_ever_returns_minus_one_zero_or_one():
    for difficulty in Difficulty:
        # simulate() asserts each direction is in (-1, 0, 1) on every frame.
        simulate(difficulty, seed=7)


def test_controller_does_not_import_paddle_or_ball_classes():
    tree = ast.parse(AI_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.startswith("pong.") for name in imported)


def look_frames(difficulty, dt, frames=200):
    """Return the frame numbers on which the controller took a new look.

    A look is seen as a call to rng.uniform(), which happens once per look.
    """
    rng = FixedOffsetRandom(0.0)
    ctrl = AIController(difficulty, rng)
    looks = []
    for frame in range(frames):
        before = len(rng.calls)
        ctrl.update(dt, 0.0, 0.0)
        if len(rng.calls) > before:
            looks.append(frame)
    return looks


@pytest.mark.parametrize(
    ("difficulty", "dt", "expected_frames"),
    [
        # 1/60 s steps (the game's frame rate). Delays from the issue: 0.10, 0.25, 0.40 s.
        (Difficulty.HARD, 1 / 60, 6),
        (Difficulty.MEDIUM, 1 / 60, 15),
        (Difficulty.EASY, 1 / 60, 24),
        # 1/120 s steps. Every delay is a whole number of frames.
        (Difficulty.HARD, 1 / 120, 12),
        (Difficulty.MEDIUM, 1 / 120, 30),
        (Difficulty.EASY, 1 / 120, 48),
        # 1/50 s steps. Medium's 0.25 s is 12.5 frames, so the first look at or
        # after 0.25 s is on the 13th frame (0.26 s).
        (Difficulty.HARD, 1 / 50, 5),
        (Difficulty.MEDIUM, 1 / 50, 13),
        (Difficulty.EASY, 1 / 50, 20),
    ],
)
def test_looks_are_spaced_by_the_expected_number_of_frames(
    difficulty, dt, expected_frames
):
    looks = look_frames(difficulty, dt)
    assert looks[0] == 0
    gaps = [later - earlier for earlier, later in itertools.pairwise(looks)]
    assert len(gaps) >= 4
    assert gaps == [expected_frames] * len(gaps)
