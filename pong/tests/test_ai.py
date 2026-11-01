import ast
import dataclasses
import itertools
import math
import random
from pathlib import Path

import pytest

from pong.ai import (
    AI_SETTINGS,
    AIM_SMOOTHING_TIME,
    DEAD_ZONE,
    AIController,
    AISettings,
    Difficulty,
    predict_contact_y,
)
from pong.game import GameEvent, Match, Mode, Player
from pong.physics import Ball, Paddle
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH

AI_SOURCE = Path(__file__).parent.parent / "ai.py"

BALL_RADIUS = 8.0
AI_PADDLE_X = 958.0
"""Left edge of the right-hand paddle, as ``Match`` places it."""
DT = 1 / 60


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


class SequenceRandom(random.Random):
    """A random source whose uniform() returns the given values in order."""

    def __init__(self, values: list[float]) -> None:
        super().__init__(0)
        self.values = list(values)

    def uniform(self, a: float, b: float) -> float:
        return self.values.pop(0)


def look(
    ctrl,
    dt,
    ball_y,
    paddle_y,
    *,
    ball_x=500.0,
    vx=0.0,
    vy=0.0,
    paddle_x=AI_PADDLE_X,
):
    """Call ``ctrl.update`` with a ball at ``(ball_x, ball_y)`` moving at ``(vx, vy)``.

    ``paddle_y`` is the AI paddle's centre y. The playfield is the game's.
    """
    return ctrl.update(
        dt,
        ball_x,
        ball_y,
        vx,
        vy,
        BALL_RADIUS,
        paddle_x,
        paddle_y,
        PLAYFIELD_HEIGHT,
    )


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
        result = look(ctrl, 1 / 60, ball_y, paddle_y)
        assert type(result) is int
        assert result in (-1, 0, 1)


def test_first_update_takes_a_look_even_with_zero_dt(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    # Ball is well below the paddle, so the first look must aim down.
    assert look(ctrl, 0.0, 300.0, 100.0) == 1


def test_no_new_look_before_reaction_delay(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert look(ctrl, 0.0, 100.0, 0.0) == 1  # look 1: aim at 100
    # Ball moves to 0 but the controller still aims at 100 until 0.5 s passes.
    assert look(ctrl, 0.25, 0.0, 0.0) == 1
    assert look(ctrl, 0.2, 0.0, 0.0) == 1


def test_new_look_once_reaction_delay_has_passed(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    look(ctrl, 0.0, 100.0, 0.0)  # look 1: aim at 100
    look(ctrl, 0.25, 0.0, 0.0)
    # 0.5 s since look 1 has passed, so this call looks at the ball at 0.
    assert look(ctrl, 0.25, 0.0, 0.0) == 0


def test_reaction_delay_counts_from_the_last_look(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    look(ctrl, 0.0, 100.0, 0.0)  # look 1 aims at 100
    look(ctrl, 0.5, 0.0, 0.0)  # look 2 aims at 0
    # Ball moves back to 100. Only 0.25 s since look 2, so still aiming at 0.
    assert look(ctrl, 0.25, 100.0, 0.0) == 0


def test_zero_dt_never_takes_a_new_look(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert look(ctrl, 0.0, 100.0, 0.0) == 1  # look 1 aims at 100
    for _ in range(10):
        # Ball jumps to 0 but no time passes, so the target stays at 100.
        assert look(ctrl, 0.0, 0.0, 0.0) == 1


def test_between_looks_the_direction_follows_the_paddle(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    assert look(ctrl, 0.0, 100.0, 0.0) == 1  # aim at 100, paddle above
    assert look(ctrl, 0.1, 100.0, 90.0) == 1  # still aiming at 100
    assert look(ctrl, 0.1, 100.0, 100.0) == 0  # paddle reached the target
    assert look(ctrl, 0.1, 100.0, 120.0) == -1  # paddle overshot


def test_each_look_draws_offset_uniformly_over_aim_error(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=10.0)
    rng = FixedOffsetRandom(0.0)
    ctrl = AIController(Difficulty.HARD, rng)
    look(ctrl, 0.0, 100.0, 100.0)  # look 1
    look(ctrl, 0.5, 100.0, 100.0)  # look 2
    assert rng.calls == [(-10.0, 10.0), (-10.0, 10.0)]


def test_target_is_seen_ball_y_plus_offset(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=10.0)
    # Offset +10: target is 110. Paddle at 105 is 5 px above it, so move down.
    ctrl = AIController(Difficulty.HARD, FixedOffsetRandom(10.0))
    assert look(ctrl, 0.0, 100.0, 105.0) == 1
    # Paddle at 107 is only 3 px above the target, inside the dead zone.
    ctrl = AIController(Difficulty.HARD, FixedOffsetRandom(10.0))
    assert look(ctrl, 0.0, 100.0, 107.0) == 0
    # Offset -10: target is 90. Paddle at 95 is 5 px below it, so move up.
    ctrl = AIController(Difficulty.HARD, FixedOffsetRandom(-10.0))
    assert look(ctrl, 0.0, 100.0, 95.0) == -1


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
    assert look(ctrl, 0.0, 100.0, paddle_y) == expected


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
        direction = look(ctrl, dt, ball_y, paddle_y)
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
        look(ctrl, dt, 0.0, 0.0)
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


# Fixed-path jitter: a ball whose y never changes, stepped with pong/physics.py.

BALL_Y = 300.0
FIXED_FRAMES = 600


def run_fixed_path(difficulty, seed, start=100.0):
    """Step an AI paddle against a ball that stays at ``BALL_Y``.

    Returns the paddle's direction on each frame and its centre before each move.
    """
    ball = Ball(500.0, BALL_Y, 0.0, 0.0, radius=BALL_RADIUS)
    paddle = Paddle(AI_PADDLE_X, start - 50, speed=AI_SETTINGS[difficulty].max_speed)
    ctrl = AIController(difficulty, random.Random(seed))
    directions = []
    centres = []
    for _ in range(FIXED_FRAMES):
        centre = paddle.y + paddle.height / 2
        direction = look(ctrl, DT, ball.y, centre)
        directions.append(direction)
        centres.append(centre)
        paddle.move(direction, DT, PLAYFIELD_HEIGHT)
        ball.step(DT, PLAYFIELD_HEIGHT)
    return directions, centres


def count_reversals(directions):
    """Count sign changes between consecutive non-zero moves. Holds are skipped."""
    moves = [d for d in directions if d != 0]
    return sum(1 for a, b in itertools.pairwise(moves) if a != b)


@pytest.mark.parametrize("difficulty", list(Difficulty))
def test_no_reversal_on_consecutive_frames_inside_dead_zone(monkeypatch, difficulty):
    use_settings(monkeypatch, difficulty, aim_error=0.0)
    directions, centres = run_fixed_path(difficulty, seed=0)
    for k in range(len(directions) - 1):
        both_inside = (
            abs(centres[k] - BALL_Y) <= DEAD_ZONE
            and abs(centres[k + 1] - BALL_Y) <= DEAD_ZONE
        )
        if both_inside:
            assert directions[k] * directions[k + 1] >= 0, f"frame {k}"


@pytest.mark.parametrize("difficulty", list(Difficulty))
def test_fixed_path_reverses_at_most_once_with_no_aim_error(monkeypatch, difficulty):
    use_settings(monkeypatch, difficulty, aim_error=0.0)
    directions, _ = run_fixed_path(difficulty, seed=0)
    assert count_reversals(directions) <= 1


@pytest.mark.parametrize("difficulty", list(Difficulty))
@pytest.mark.parametrize("seed", range(10))
def test_fixed_path_reverses_at_most_twice_with_default_aim(difficulty, seed):
    directions, _ = run_fixed_path(difficulty, seed=seed)
    assert count_reversals(directions) <= 2


def test_aim_error_eases_toward_each_new_draw(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=10.0)
    ctrl = AIController(Difficulty.HARD, SequenceRandom([10.0, -10.0]))
    look(ctrl, 0.0, 100.0, 100.0)  # first look takes the first draw at once
    assert ctrl.target == pytest.approx(110.0)
    look(ctrl, 0.5, 100.0, 100.0)  # second look draws -10 and eases toward it
    eased = 10.0 + (-10.0 - 10.0) * (1 - math.exp(-0.5 / AIM_SMOOTHING_TIME))
    assert ctrl.target == pytest.approx(100.0 + eased)
    assert ctrl.target > 100.0 - 10.0


# Hard prediction: the y where the ball reaches the AI paddle's face.


PADDLE_CENTRE_MIN = 50.0
"""Lowest centre a 100 px paddle can reach: its half height from the top."""
PADDLE_CENTRE_MAX = PLAYFIELD_HEIGHT - 50.0
"""Highest centre a 100 px paddle can reach."""


def contact_x():
    """The ball centre x at which ``segment_hits_paddle`` first counts a hit."""
    return AI_PADDLE_X - BALL_RADIUS


def physics_y_at_contact(ball_x, ball_y, vx, vy):
    """Return the ball's y at the contact x, using pong/physics.py bounces."""
    ball = Ball(ball_x, ball_y, vx, vy, radius=BALL_RADIUS)
    ball.step((contact_x() - ball_x) / vx, PLAYFIELD_HEIGHT)
    return ball.y


def hard_centre_at_contact(ball_x, ball_y, vx, vy, paddle_centre):
    """Run Hard with no aim error until the ball reaches the contact x.

    Returns the AI paddle's centre at that moment.
    """
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    ball = Ball(ball_x, ball_y, vx, vy, radius=BALL_RADIUS)
    paddle = Paddle(
        AI_PADDLE_X,
        paddle_centre - 50,
        speed=AI_SETTINGS[Difficulty.HARD].max_speed,
    )
    while ball.x < contact_x():
        direction = look(
            ctrl,
            DT,
            ball.y,
            paddle.y + paddle.height / 2,
            ball_x=ball.x,
            vx=ball.vx,
            vy=ball.vy,
        )
        paddle.move(direction, DT, PLAYFIELD_HEIGHT)
        ball.step(DT, PLAYFIELD_HEIGHT)
    return paddle.y + paddle.height / 2


@pytest.fixture
def hard_without_aim_error(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, aim_error=0.0)


@pytest.mark.parametrize(
    ("ball_x", "ball_y", "vx", "vy", "paddle_centre"),
    [
        pytest.param(500.0, 300.0, 300.0, 60.0, 300.0, id="no-bounce"),
        pytest.param(500.0, 500.0, 300.0, 200.0, 300.0, id="one-bounce"),
        pytest.param(100.0, 200.0, 300.0, 700.0, 300.0, id="several-bounces"),
        pytest.param(500.0, 300.0, 40.0, 300.0, 300.0, id="nearly-vertical"),
    ],
)
def test_hard_lines_up_with_predicted_contact_y(
    hard_without_aim_error, ball_x, ball_y, vx, vy, paddle_centre
):
    expected = physics_y_at_contact(ball_x, ball_y, vx, vy)
    # The case is fair only if the paddle can reach the predicted centre in time.
    time_to_contact = (contact_x() - ball_x) / vx
    max_speed = AI_SETTINGS[Difficulty.HARD].max_speed
    assert max_speed * time_to_contact >= abs(expected - paddle_centre)
    assert PADDLE_CENTRE_MIN <= expected <= PADDLE_CENTRE_MAX
    centre = hard_centre_at_contact(ball_x, ball_y, vx, vy, paddle_centre)
    assert centre == pytest.approx(expected, abs=DEAD_ZONE)


def test_predict_contact_y_matches_physics_for_one_bounce():
    predicted = predict_contact_y(
        500.0, 500.0, 300.0, 200.0, BALL_RADIUS, AI_PADDLE_X, PLAYFIELD_HEIGHT
    )
    assert predicted == pytest.approx(physics_y_at_contact(500.0, 500.0, 300.0, 200.0))


@pytest.mark.parametrize(
    ("ball_y", "vy", "target"),
    [
        pytest.param(20.0, 0.0, 50.0, id="top-limit"),
        pytest.param(585.0, 0.0, 550.0, id="bottom-limit"),
    ],
)
def test_hard_paddle_stops_at_the_nearest_reachable_centre(
    hard_without_aim_error, ball_y, vy, target
):
    ball_x, vx = 500.0, 300.0
    centre = hard_centre_at_contact(ball_x, ball_y, vx, vy, paddle_centre=300.0)
    assert centre == pytest.approx(target, abs=DEAD_ZONE)


@pytest.mark.parametrize(
    ("ball_x", "vx"),
    [
        pytest.param(500.0, -300.0, id="moving-away"),
        pytest.param(500.0, 0.0, id="not-moving"),
        pytest.param(955.0, 300.0, id="past-contact"),
    ],
)
def test_hard_without_prediction_aims_at_ball_y(hard_without_aim_error, ball_x, vx):
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    look(ctrl, 0.0, 300.0, 300.0, ball_x=ball_x, vx=vx, vy=60.0)
    assert ctrl.target == pytest.approx(300.0)


def test_hard_aim_error_is_added_to_the_prediction(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, aim_error=10.0)
    rng = FixedOffsetRandom(7.0)
    ctrl = AIController(Difficulty.HARD, rng)
    # Ball at y 300 moving down, so the prediction is 390. The offset goes on top.
    look(ctrl, 0.0, 300.0, 300.0, vx=300.0, vy=60.0)
    assert ctrl.target == pytest.approx(397.0)
    assert rng.calls == [(-10.0, 10.0)]


def test_hard_prediction_changes_only_at_a_look(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    look(ctrl, 0.0, 300.0, 300.0, vx=300.0, vy=60.0)  # look 1: 300 + 60 * 1.5
    assert ctrl.target == pytest.approx(390.0)
    look(ctrl, 0.25, 300.0, 300.0, vx=300.0, vy=-60.0)  # 0.25 s: no look yet
    assert ctrl.target == pytest.approx(390.0)
    look(ctrl, 0.2, 300.0, 300.0, vx=300.0, vy=-60.0)  # 0.45 s: still no look
    assert ctrl.target == pytest.approx(390.0)
    look(ctrl, 0.05, 300.0, 300.0, vx=300.0, vy=-60.0)  # 0.5 s: look 2
    assert ctrl.target == pytest.approx(210.0)  # 300 - 60 * 1.5


def test_hard_zero_dt_does_not_take_a_prediction_look(monkeypatch):
    use_settings(monkeypatch, Difficulty.HARD, reaction_delay=0.5, aim_error=0.0)
    ctrl = AIController(Difficulty.HARD, random.Random(0))
    look(ctrl, 0.0, 300.0, 300.0, vx=300.0, vy=60.0)
    look(ctrl, 0.0, 300.0, 300.0, vx=300.0, vy=-60.0)
    assert ctrl.target == pytest.approx(390.0)


@pytest.mark.parametrize("difficulty", [Difficulty.EASY, Difficulty.MEDIUM])
def test_easy_and_medium_aim_at_current_ball_y(monkeypatch, difficulty):
    use_settings(monkeypatch, difficulty, aim_error=0.0)
    ctrl = AIController(difficulty, random.Random(0))
    reaction_delay = AI_SETTINGS[difficulty].reaction_delay
    ball_y = 300.0
    for _ in range(5):
        # Each call is a look, since dt equals the reaction delay.
        look(ctrl, reaction_delay, ball_y, 300.0, vx=300.0, vy=60.0)
        assert ctrl.target == pytest.approx(ball_y)
        predicted = predict_contact_y(
            500.0, ball_y, 300.0, 60.0, BALL_RADIUS, AI_PADDLE_X, PLAYFIELD_HEIGHT
        )
        assert predicted is not None
        assert ctrl.target != pytest.approx(predicted)
        ball_y += 25.0


# Seeded rallies: Hard against Easy, using the match rules in pong/game.py.

RALLY_FRAMES = 3600
RALLY_SEEDS = 200


def play_rally(seed, hard_on_left):
    """Play one serve-to-point rally between two AIs.

    Returns ``True`` if Hard won, ``False`` if Easy won, and ``None`` if no one
    scored within ``RALLY_FRAMES``. The left AI sees the field mirrored, so the
    same controller code aims at a paddle on its right.
    """
    left = Difficulty.HARD if hard_on_left else Difficulty.EASY
    right = Difficulty.EASY if hard_on_left else Difficulty.HARD
    match = Match(Mode.TWO_PLAYER, Difficulty.EASY)
    # Match sets P2's speed from the difficulty only in single-player, so set both here.
    match.p1.speed = AI_SETTINGS[left].max_speed
    match.p2.speed = AI_SETTINGS[right].max_speed
    left_ai = AIController(left, random.Random(2 * seed))
    right_ai = AIController(right, random.Random(2 * seed + 1))
    mirrored_paddle_x = PLAYFIELD_WIDTH - (match.p1.x + match.p1.width)
    match.start_rally()
    for _ in range(RALLY_FRAMES):
        ball = match.ball
        d1 = look(
            left_ai,
            DT,
            ball.y,
            match.p1.y + match.p1.height / 2,
            ball_x=PLAYFIELD_WIDTH - ball.x,
            vx=-ball.vx,
            vy=ball.vy,
            paddle_x=mirrored_paddle_x,
        )
        d2 = look(
            right_ai,
            DT,
            ball.y,
            match.p2.y + match.p2.height / 2,
            ball_x=ball.x,
            vx=ball.vx,
            vy=ball.vy,
        )
        p1_before = match.score.points(Player.P1)
        events = match.update(DT, d1, d2)
        if GameEvent.SCORE in events:
            p1_scored = match.score.points(Player.P1) > p1_before
            return p1_scored == hard_on_left
    return None


def test_hard_wins_more_seeded_rallies_than_easy():
    hard_wins = 0
    easy_wins = 0
    for seed in range(RALLY_SEEDS):
        winner = play_rally(seed, hard_on_left=seed % 2 == 1)
        if winner is True:
            hard_wins += 1
        elif winner is False:
            easy_wins += 1
    assert hard_wins > easy_wins
