import ast
from pathlib import Path

import pytest

from pong.physics import Ball, Paddle

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
