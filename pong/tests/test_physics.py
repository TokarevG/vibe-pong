import ast
import math
from pathlib import Path

import pytest

from pong.physics import (
    MAX_BOUNCE_ANGLE_DEGREES,
    MAX_SPEED,
    PADDLE_INFLUENCE,
    SERVE_SPEED,
    SPEED_GAIN,
    Ball,
    Paddle,
    ball_hits_paddle,
    bounce_velocity,
    next_speed,
    segment_hits_paddle,
)

PHYSICS_SOURCE = Path(__file__).parent.parent / "physics.py"
FIELD_HEIGHT = 600


def test_module_does_not_import_pygame():
    tree = ast.parse(PHYSICS_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "pygame" for name in imported)


def test_default_size_and_speed():
    paddle = Paddle(10, 20)
    assert paddle.x == 10
    assert paddle.y == 20
    assert paddle.width == 12
    assert paddle.height == 100
    assert paddle.speed == 420.0


def test_custom_speed_is_used():
    paddle = Paddle(0, 100, speed=300.0)
    paddle.move(1, 0.5, FIELD_HEIGHT)
    assert paddle.y == pytest.approx(250.0)


def test_move_down_by_direction_speed_dt():
    paddle = Paddle(0, 100)
    paddle.move(1, 0.5, FIELD_HEIGHT)
    assert paddle.y == pytest.approx(100 + 210)


def test_move_up_by_direction_speed_dt():
    paddle = Paddle(0, 300)
    paddle.move(-1, 0.5, FIELD_HEIGHT)
    assert paddle.y == pytest.approx(300 - 210)


def test_direction_zero_leaves_y_unchanged_for_any_dt():
    paddle = Paddle(0, 250)
    for dt in (0.0, 0.016, 0.5, 10.0):
        paddle.move(0, dt, FIELD_HEIGHT)
        assert paddle.y == 250


@pytest.mark.parametrize("direction", [2, -2, 0.5, 5])
def test_invalid_direction_raises(direction):
    paddle = Paddle(0, 100)
    with pytest.raises(ValueError):
        paddle.move(direction, 0.1, FIELD_HEIGHT)
    assert paddle.y == 100


def test_negative_dt_raises():
    paddle = Paddle(0, 100)
    with pytest.raises(ValueError):
        paddle.move(1, -0.1, FIELD_HEIGHT)
    assert paddle.y == 100


def test_top_edge_clamps_to_zero():
    paddle = Paddle(0, 10)
    paddle.move(-1, 0.1, FIELD_HEIGHT)
    assert paddle.y == 0


def test_bottom_edge_clamps_to_field_height_minus_height():
    paddle = Paddle(0, 480)
    paddle.move(1, 0.1, FIELD_HEIGHT)
    assert paddle.y == FIELD_HEIGHT - paddle.height


def test_large_dt_stops_exactly_on_top_edge():
    paddle = Paddle(0, 200)
    paddle.move(-1, 100.0, FIELD_HEIGHT)
    assert paddle.y == 0


def test_large_dt_stops_exactly_on_bottom_edge():
    paddle = Paddle(0, 200)
    paddle.move(1, 100.0, FIELD_HEIGHT)
    assert paddle.y + paddle.height == FIELD_HEIGHT


def test_pushing_into_edge_again_stays_on_edge():
    paddle = Paddle(0, 0)
    paddle.move(-1, 0.5, FIELD_HEIGHT)
    assert paddle.y == 0
    paddle.move(-1, 0.5, FIELD_HEIGHT)
    assert paddle.y == 0
    paddle.move(1, 10.0, FIELD_HEIGHT)
    paddle.move(1, 10.0, FIELD_HEIGHT)
    assert paddle.y + paddle.height == FIELD_HEIGHT


def test_velocity_is_applied_velocity_when_moving_freely():
    paddle = Paddle(0, 100)
    paddle.move(1, 0.5, FIELD_HEIGHT)
    assert paddle.velocity == pytest.approx(420.0)
    paddle.move(-1, 0.25, FIELD_HEIGHT)
    assert paddle.velocity == pytest.approx(-420.0)


def test_velocity_is_zero_when_held_against_edge():
    paddle = Paddle(0, 0)
    paddle.move(-1, 0.5, FIELD_HEIGHT)
    assert paddle.velocity == 0

    paddle = Paddle(0, FIELD_HEIGHT - 100)
    paddle.move(1, 0.5, FIELD_HEIGHT)
    assert paddle.velocity == 0


def test_velocity_reflects_partial_move_into_edge():
    paddle = Paddle(0, 50)
    paddle.move(-1, 0.2, FIELD_HEIGHT)
    assert paddle.y == 0
    assert paddle.velocity == pytest.approx(-50 / 0.2)


def test_velocity_is_zero_when_direction_is_zero():
    paddle = Paddle(0, 100)
    paddle.move(1, 0.1, FIELD_HEIGHT)
    paddle.move(0, 0.1, FIELD_HEIGHT)
    assert paddle.velocity == 0


def test_velocity_is_zero_when_dt_is_zero():
    paddle = Paddle(0, 100)
    paddle.move(1, 0.0, FIELD_HEIGHT)
    assert paddle.y == 100
    assert paddle.velocity == 0


BALL_RADIUS = 8


def test_ball_defaults_radius_to_8():
    ball = Ball(500, 300, 300, 0)
    assert ball.radius == 8
    assert ball.x == 500
    assert ball.y == 300
    assert ball.vx == 300
    assert ball.vy == 0


def test_ball_straight_line_move():
    ball = Ball(500, 300, 300, 0)
    bounced = ball.step(0.1, FIELD_HEIGHT)
    assert ball.x == pytest.approx(530)
    assert ball.y == pytest.approx(300)
    assert ball.vx == 300
    assert ball.vy == 0
    assert bounced is False


def test_ball_moves_by_velocity_times_dt_on_both_axes():
    ball = Ball(100, 200, 50, -40)
    ball.step(0.5, FIELD_HEIGHT)
    assert ball.x == pytest.approx(125)
    assert ball.y == pytest.approx(180)


def test_ball_top_bounce_reflects_centre_and_flips_vy():
    ball = Ball(500, 5, 0, -100)
    bounced = ball.step(0.1, FIELD_HEIGHT)
    assert ball.y == pytest.approx(21)
    assert ball.vy == pytest.approx(100)
    assert bounced is True


def test_ball_top_bounce_does_not_change_vx():
    ball = Ball(500, 5, 300, -100)
    ball.step(0.1, FIELD_HEIGHT)
    assert ball.vx == 300


def test_ball_bottom_bounce_reflects_centre_and_flips_vy():
    ball = Ball(500, 595, 0, 100)
    bounced = ball.step(0.1, FIELD_HEIGHT)
    # y_raw = 605, reflected = 2 * (600 - 8) - 605 = 579
    assert ball.y == pytest.approx(579)
    assert ball.vy == pytest.approx(-100)
    assert bounced is True


def test_ball_bottom_bounce_does_not_change_vx():
    ball = Ball(500, 595, -250, 100)
    ball.step(0.1, FIELD_HEIGHT)
    assert ball.vx == -250


def test_ball_reaching_top_wall_exactly_is_not_a_bounce():
    # dt is a power of two so the arithmetic is exact: 23 + (-120 * 0.125) == 8
    ball = Ball(500, 23, 0, -120)
    bounced = ball.step(0.125, FIELD_HEIGHT)
    assert ball.y == BALL_RADIUS
    assert ball.vy == -120
    assert bounced is False


def test_ball_reaching_bottom_wall_exactly_is_not_a_bounce():
    # 577 + 120 * 0.125 == 592
    ball = Ball(500, 577, 0, 120)
    bounced = ball.step(0.125, FIELD_HEIGHT)
    assert ball.y == FIELD_HEIGHT - BALL_RADIUS
    assert ball.vy == 120
    assert bounced is False


def test_ball_step_crossing_both_walls_ends_inside():
    ball = Ball(500, 300, 0, 5000)
    bounced = ball.step(0.1, FIELD_HEIGHT)
    assert BALL_RADIUS <= ball.y <= FIELD_HEIGHT - BALL_RADIUS
    assert bounced is True


def test_ball_huge_step_reflects_until_inside():
    # 300 + 1000 = 1300 -> bottom wall (592) -> -116 -> top wall (8) -> 132
    ball = Ball(500, 300, 0, 1000)
    ball.step(1.0, FIELD_HEIGHT)
    assert ball.y == pytest.approx(132)


def test_ball_vy_sign_follows_number_of_wall_crossings():
    # Two wall crossings (bottom then top) flip vy twice, so its sign is kept.
    ball = Ball(500, 300, 0, 1000)
    ball.step(1.0, FIELD_HEIGHT)
    assert ball.vy == pytest.approx(1000)


@pytest.mark.parametrize("dt", [0.0, 0.016, 0.5, 3.7])
def test_ball_centre_stays_in_range_for_any_dt(dt):
    ball = Ball(500, 300, 0, 777)
    ball.step(dt, FIELD_HEIGHT)
    assert BALL_RADIUS <= ball.y <= FIELD_HEIGHT - BALL_RADIUS


def test_ball_zero_dt_does_not_move_or_bounce():
    ball = Ball(500, 300, 300, 200)
    bounced = ball.step(0.0, FIELD_HEIGHT)
    assert ball.x == 500
    assert ball.y == 300
    assert ball.vy == 200
    assert bounced is False


def test_ball_negative_dt_raises():
    ball = Ball(500, 300, 300, 0)
    with pytest.raises(ValueError):
        ball.step(-0.1, FIELD_HEIGHT)


def test_ball_playfield_not_taller_than_diameter_raises():
    ball = Ball(500, 8, 0, 0)
    with pytest.raises(ValueError):
        ball.step(0.1, 2 * BALL_RADIUS)


INFINITY = float("inf")


@pytest.mark.parametrize("dt", [INFINITY, 1e9, 1e300])
def test_ball_huge_dt_returns_centre_inside_range(dt):
    ball = Ball(500, 300, 0, 1)
    bounced = ball.step(dt, FIELD_HEIGHT)
    assert BALL_RADIUS <= ball.y <= FIELD_HEIGHT - BALL_RADIUS
    assert ball.vx == 0
    assert bounced is True


def test_ball_infinite_dt_with_nonzero_vy_returns_quickly():
    # The old per-bounce loop never ended for an infinite step.
    ball = Ball(500, 300, 0, -1000)
    ball.step(INFINITY, FIELD_HEIGHT)
    assert BALL_RADIUS <= ball.y <= FIELD_HEIGHT - BALL_RADIUS


def test_ball_huge_travel_from_overflow_returns_centre_inside_range():
    # vy * dt overflows to infinity even though dt is finite.
    ball = Ball(500, 300, 0, 1e308)
    bounced = ball.step(10.0, FIELD_HEIGHT)
    assert BALL_RADIUS <= ball.y <= FIELD_HEIGHT - BALL_RADIUS
    assert bounced is True


def test_ball_infinite_dt_with_zero_vy_does_not_move():
    ball = Ball(500, 300, 0, 0)
    bounced = ball.step(INFINITY, FIELD_HEIGHT)
    assert ball.y == 300
    assert ball.vy == 0
    assert bounced is False


def test_ball_nan_dt_raises_and_leaves_ball_unchanged():
    ball = Ball(500, 300, 300, 200)
    with pytest.raises(ValueError):
        ball.step(float("nan"), FIELD_HEIGHT)
    assert ball.x == 500
    assert ball.y == 300
    assert ball.vy == 200


# Paddle collision: ball_hits_paddle(ball_x, ball_y, ball_radius,
#                                    paddle_x, paddle_y, paddle_w, paddle_h, ball_vx)
RADIUS = 8


def test_direct_hit_on_left_paddle_moving_toward_it_is_true():
    # Paddle 50..62 in x, 200..300 in y; ball centre 6 px from its right face.
    assert ball_hits_paddle(68, 250, RADIUS, 50, 200, 12, 100, -300) is True


def test_direct_hit_on_right_paddle_moving_toward_it_is_true():
    # Paddle 900..912 in x; ball centre 4 px from its left face.
    assert ball_hits_paddle(896, 250, RADIUS, 900, 200, 12, 100, 300) is True


def test_miss_above_paddle_is_false():
    # Nearest point is (62, 200); distance sqrt(36 + 81) > 8.
    assert ball_hits_paddle(68, 191, RADIUS, 50, 200, 12, 100, -300) is False


def test_miss_below_paddle_is_false():
    # Nearest point is (62, 300); distance sqrt(36 + 81) > 8.
    assert ball_hits_paddle(68, 309, RADIUS, 50, 200, 12, 100, -300) is False


def test_clearly_above_and_below_paddle_is_false():
    assert ball_hits_paddle(56, 150, RADIUS, 50, 200, 12, 100, -300) is False
    assert ball_hits_paddle(56, 350, RADIUS, 50, 200, 12, 100, -300) is False


def test_overlapping_ball_moving_away_is_false():
    # Left paddle, ball overlaps it but moves right (away).
    assert ball_hits_paddle(68, 250, RADIUS, 50, 200, 12, 100, 300) is False
    # Right paddle, ball overlaps it but moves left (away).
    assert ball_hits_paddle(896, 250, RADIUS, 900, 200, 12, 100, -300) is False


def test_zero_vx_is_never_a_hit():
    assert ball_hits_paddle(68, 250, RADIUS, 50, 200, 12, 100, 0) is False
    assert ball_hits_paddle(896, 250, RADIUS, 900, 200, 12, 100, 0) is False


def test_boundary_exactly_one_radius_from_corner_is_hit():
    # Top-left corner of the right paddle is (900, 200); centre 8 px to its left.
    assert ball_hits_paddle(892, 200, RADIUS, 900, 200, 12, 100, 300) is True


def test_boundary_one_pixel_farther_is_miss():
    assert ball_hits_paddle(891, 200, RADIUS, 900, 200, 12, 100, 300) is False


def test_hit_check_does_not_change_inputs_or_objects():
    paddle = Paddle(50, 200, width=12, height=100)
    ball = Ball(68, 250, -300, 0)
    first = ball_hits_paddle(
        ball.x,
        ball.y,
        ball.radius,
        paddle.x,
        paddle.y,
        paddle.width,
        paddle.height,
        ball.vx,
    )
    second = ball_hits_paddle(
        ball.x,
        ball.y,
        ball.radius,
        paddle.x,
        paddle.y,
        paddle.width,
        paddle.height,
        ball.vx,
    )
    assert first is True and second is True
    assert (ball.x, ball.y, ball.vx, ball.vy, ball.radius) == (68, 250, -300, 0, 8)
    assert (paddle.x, paddle.y, paddle.width, paddle.height) == (50, 200, 12, 100)


def test_ball_overlapping_left_paddle_after_crossing_its_centre_is_hit():
    # Amended #6 example: ball centre (30) is on the paddle centre x (30).
    assert ball_hits_paddle(30, 300, RADIUS, 24, 270, 12, 60, -900) is True


@pytest.mark.parametrize("vx", [-700, -900])
def test_qa_repro_ball_at_x50_overlapping_p1_moving_left_is_hit(vx):
    # P1 is at (30, 250), 12 wide, 100 tall. Its right face is at x 42, so a
    # ball at x 50 with radius 8 just touches it. The side is set by the
    # midline, so the hit does not depend on the ball centre passing P1's centre x (36).
    assert ball_hits_paddle(50, 300, RADIUS, 30, 250, 12, 100, vx) is True


def test_ball_on_right_side_moving_left_is_not_a_hit():
    # Right paddle centre x is 906, so it is on the right side; moving left is away.
    assert ball_hits_paddle(896, 250, RADIUS, 900, 200, 12, 100, -900) is False
    assert ball_hits_paddle(896, 250, RADIUS, 900, 200, 12, 100, -1) is False


@pytest.mark.parametrize("paddle_x", [30, 900])
def test_zero_vx_is_never_a_hit_even_when_overlapping(paddle_x):
    assert (
        ball_hits_paddle(paddle_x + 14, 250, RADIUS, paddle_x, 200, 12, 100, 0) is False
    )


def test_max_bounce_angle_is_60_degrees():
    assert MAX_BOUNCE_ANGLE_DEGREES == 60.0


def test_bounce_velocity_returns_tuple():
    result = bounce_velocity(0.5, 300.0, 1)
    assert isinstance(result, tuple)
    assert len(result) == 2


@pytest.mark.parametrize("direction", [0, 2, -2, 0.5, None])
def test_bounce_velocity_invalid_direction_raises(direction):
    with pytest.raises(ValueError):
        bounce_velocity(0.0, 300.0, direction)


def test_bounce_velocity_negative_speed_raises():
    with pytest.raises(ValueError):
        bounce_velocity(0.0, -1.0, 1)


def test_bounce_velocity_zero_speed_gives_zero_velocity():
    assert bounce_velocity(0.7, 0.0, 1) == pytest.approx((0.0, 0.0))


def test_bounce_velocity_center_hit_is_horizontal_right():
    vx, vy = bounce_velocity(0.0, 300.0, 1)
    assert vy == 0
    assert abs(vx) == 300.0
    assert vx > 0


def test_bounce_velocity_center_hit_is_horizontal_left():
    vx, vy = bounce_velocity(0.0, 300.0, -1)
    assert vy == 0
    assert abs(vx) == 300.0
    assert vx < 0


def test_bounce_velocity_bottom_edge_is_60_degrees_down():
    vx, vy = bounce_velocity(1.0, 300.0, 1)
    assert vx == pytest.approx(300.0 * math.cos(math.radians(60)))
    assert vy == pytest.approx(300.0 * math.sin(math.radians(60)))
    assert vy > 0
    assert abs(vy) / abs(vx) == pytest.approx(1.732, abs=1e-3)


def test_bounce_velocity_top_edge_is_60_degrees_up():
    vx, vy = bounce_velocity(-1.0, 300.0, 1)
    assert vx == pytest.approx(300.0 * math.cos(math.radians(60)))
    assert vy == pytest.approx(-300.0 * math.sin(math.radians(60)))
    assert vy < 0
    assert abs(vy) / abs(vx) == pytest.approx(1.732, abs=1e-3)


def test_bounce_velocity_top_edge_sends_ball_up_for_left_return():
    vx, vy = bounce_velocity(-1.0, 300.0, -1)
    assert vx < 0
    assert vy < 0


def test_bounce_velocity_angle_is_linear_in_offset():
    _, vy_half = bounce_velocity(0.5, 300.0, 1)
    vx_half, _ = bounce_velocity(0.5, 300.0, 1)
    angle_half = math.degrees(math.atan2(vy_half, vx_half))
    assert angle_half == pytest.approx(0.5 * MAX_BOUNCE_ANGLE_DEGREES)


@pytest.mark.parametrize("offset", [0.1, 0.25, 0.5, 0.9, 1.0])
@pytest.mark.parametrize("direction", [1, -1])
def test_bounce_velocity_opposite_offsets_mirror_vy(offset, direction):
    vx_pos, vy_pos = bounce_velocity(offset, 300.0, direction)
    vx_neg, vy_neg = bounce_velocity(-offset, 300.0, direction)
    assert vx_neg == pytest.approx(vx_pos)
    assert vy_neg == pytest.approx(-vy_pos)


@pytest.mark.parametrize("offset", [-1.0, -0.6, -0.2, 0.0, 0.3, 0.8, 1.0])
@pytest.mark.parametrize("direction", [1, -1])
@pytest.mark.parametrize("speed", [1.0, 300.0, 1234.5])
def test_bounce_velocity_preserves_speed(offset, direction, speed):
    vx, vy = bounce_velocity(offset, speed, direction)
    assert math.hypot(vx, vy) == pytest.approx(speed)


@pytest.mark.parametrize("offset", [-5.0, -1.5, 1.0001, 2.0, 1e9])
def test_bounce_velocity_offset_outside_range_is_clamped(offset):
    clamped = max(-1.0, min(1.0, offset))
    assert bounce_velocity(offset, 300.0, 1) == pytest.approx(
        bounce_velocity(clamped, 300.0, 1)
    )


def test_bounce_velocity_direction_sets_sign_of_vx_only():
    vx_r, vy_r = bounce_velocity(0.4, 300.0, 1)
    vx_l, vy_l = bounce_velocity(0.4, 300.0, -1)
    assert vx_l == pytest.approx(-vx_r)
    assert vy_l == pytest.approx(vy_r)


def test_paddle_influence_is_a_quarter():
    assert PADDLE_INFLUENCE == 0.25


def test_bounce_velocity_paddle_vy_defaults_to_zero():
    assert bounce_velocity(0.3, 300.0, 1) == bounce_velocity(
        0.3, 300.0, 1, paddle_vy=0.0
    )


@pytest.mark.parametrize("offset", [-1.0, -0.4, 0.0, 0.5, 1.0])
@pytest.mark.parametrize("direction", [1, -1])
@pytest.mark.parametrize("speed", [0.0, 300.0])
def test_stationary_paddle_matches_bounce_without_paddle_vy(offset, direction, speed):
    assert bounce_velocity(offset, speed, direction, paddle_vy=0.0) == (
        bounce_velocity(offset, speed, direction)
    )


def test_paddle_moving_down_center_hit_sends_ball_down():
    _, vy = bounce_velocity(0.0, 300.0, 1, paddle_vy=400.0)
    assert vy > 0


def test_paddle_moving_up_center_hit_sends_ball_up():
    _, vy = bounce_velocity(0.0, 300.0, 1, paddle_vy=-400.0)
    assert vy < 0


def test_paddle_moving_down_center_hit_has_expected_vy():
    # Unscaled vy is PADDLE_INFLUENCE * paddle_vy, then scaled to the speed.
    speed, paddle_vy = 300.0, 400.0
    raw_vy = PADDLE_INFLUENCE * paddle_vy
    expected_vy = speed * raw_vy / math.hypot(speed, raw_vy)
    vx, vy = bounce_velocity(0.0, speed, 1, paddle_vy=paddle_vy)
    assert vy == pytest.approx(expected_vy)
    assert vx == pytest.approx(speed * speed / math.hypot(speed, raw_vy))


@pytest.mark.parametrize("offset", [-1.0, -0.5, 0.0, 0.5, 1.0])
@pytest.mark.parametrize("direction", [1, -1])
@pytest.mark.parametrize("paddle_vy", [-900.0, -50.0, 50.0, 900.0])
@pytest.mark.parametrize("speed", [1.0, 300.0, 1234.5])
def test_paddle_vy_preserves_speed(offset, direction, paddle_vy, speed):
    vx, vy = bounce_velocity(offset, speed, direction, paddle_vy=paddle_vy)
    assert math.hypot(vx, vy) == pytest.approx(speed)


@pytest.mark.parametrize("offset", [-1.0, -0.5, 0.0, 0.5, 1.0])
@pytest.mark.parametrize("paddle_vy", [-900.0, 900.0])
def test_paddle_vy_does_not_change_sign_of_vx(offset, paddle_vy):
    vx_right, _ = bounce_velocity(offset, 300.0, 1, paddle_vy=paddle_vy)
    vx_left, _ = bounce_velocity(offset, 300.0, -1, paddle_vy=paddle_vy)
    assert vx_right > 0
    assert vx_left < 0


def test_paddle_vy_zero_speed_gives_zero_velocity():
    assert bounce_velocity(0.0, 0.0, 1, paddle_vy=400.0) == (0.0, 0.0)


def test_paddle_vy_is_deterministic():
    first = bounce_velocity(0.2, 300.0, -1, paddle_vy=123.0)
    second = bounce_velocity(0.2, 300.0, -1, paddle_vy=123.0)
    assert first == second


@pytest.mark.parametrize("paddle_vy", [math.inf, -math.inf, math.nan])
def test_bounce_velocity_non_finite_paddle_vy_raises(paddle_vy):
    with pytest.raises(ValueError):
        bounce_velocity(0.0, 300.0, 1, paddle_vy=paddle_vy)


def test_speed_constants():
    assert SERVE_SPEED == 300.0
    assert SPEED_GAIN == 1.05
    assert MAX_SPEED == 900.0


def test_next_speed_is_speed_times_gain_below_cap():
    assert next_speed(300.0) == pytest.approx(315.0)


def test_next_speed_compounds_over_repeated_hits():
    speed = SERVE_SPEED
    speed = next_speed(speed)
    assert speed == pytest.approx(315.0)
    speed = next_speed(speed)
    assert speed == pytest.approx(330.75)


def test_speed_is_still_below_cap_after_22_hits():
    speed = SERVE_SPEED
    for _ in range(22):
        speed = next_speed(speed)
    assert speed == pytest.approx(877.6, abs=0.1)
    assert speed < MAX_SPEED


def test_speed_reaches_exact_cap_after_23_hits():
    speed = SERVE_SPEED
    for _ in range(23):
        speed = next_speed(speed)
    assert speed == MAX_SPEED


def test_next_speed_at_cap_stays_at_cap():
    assert next_speed(900.0) == 900.0


def test_more_hits_keep_speed_at_cap():
    speed = SERVE_SPEED
    for _ in range(50):
        speed = next_speed(speed)
    assert speed == MAX_SPEED
    for _ in range(10):
        speed = next_speed(speed)
    assert speed == 900.0


@pytest.mark.parametrize(
    "speed", [0.0, 1.0, 300.0, 899.0, 900.0, 901.0, 5000.0, math.inf]
)
def test_next_speed_is_never_above_max(speed):
    assert next_speed(speed) <= MAX_SPEED


@pytest.mark.parametrize("speed", [0.0, 1.0, 300.0, 850.0])
def test_next_speed_below_cap_is_gain_times_speed(speed):
    assert next_speed(speed) == pytest.approx(speed * SPEED_GAIN)


def test_next_speed_clamps_speed_above_cap():
    assert next_speed(5000.0) == MAX_SPEED
    assert next_speed(math.inf) == MAX_SPEED


def test_next_speed_nan_raises():
    with pytest.raises(ValueError):
        next_speed(math.nan)


@pytest.mark.parametrize("speed", [-math.inf, 1e308, -1e308])
def test_next_speed_extreme_finite_or_infinite_is_never_above_max(speed):
    assert next_speed(speed) <= MAX_SPEED


# Segment test: segment_hits_paddle(x0, y0, x1, y1, ball_radius,
#                                   paddle_x, paddle_y, paddle_w, paddle_h, ball_vx)


def test_segment_passing_through_paddle_is_hit_with_both_ends_outside():
    assert segment_hits_paddle(0, 300, 60, 300, RADIUS, 30, 250, 12, 100, -300) is True


def test_segment_grazing_rounded_corner_within_radius_is_hit():
    # Corner (30, 250) is 7.5 px above the segment, closer than the radius of 8.
    assert (
        segment_hits_paddle(20, 242.5, 40, 242.5, RADIUS, 30, 250, 12, 100, -300)
        is True
    )


def test_segment_just_missing_rounded_corner_is_not_hit():
    # Corner (30, 250) is 8.5 px above the segment, farther than the radius.
    assert (
        segment_hits_paddle(20, 241.5, 40, 241.5, RADIUS, 30, 250, 12, 100, -300)
        is False
    )


def test_segment_ending_exactly_one_radius_from_face_is_hit():
    assert segment_hits_paddle(0, 300, 22, 300, RADIUS, 30, 250, 12, 100, -300) is True


def test_segment_entirely_short_of_paddle_is_not_hit():
    assert segment_hits_paddle(0, 300, 21, 300, RADIUS, 30, 250, 12, 100, -300) is False


def test_segment_moving_away_is_not_hit_even_when_overlapping():
    assert segment_hits_paddle(36, 300, 40, 300, RADIUS, 30, 250, 12, 100, 300) is False


def test_zero_length_segment_matches_point_test():
    assert segment_hits_paddle(36, 300, 36, 300, RADIUS, 30, 250, 12, 100, -300) is True
    assert (
        segment_hits_paddle(51, 300, 51, 300, RADIUS, 30, 250, 12, 100, -300) is False
    )


def test_segment_with_zero_vx_is_never_a_hit():
    assert segment_hits_paddle(36, 300, 36, 300, RADIUS, 30, 250, 12, 100, 0) is False
