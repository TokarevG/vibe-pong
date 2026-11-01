import ast
from pathlib import Path

import pytest

from pong.physics import Paddle

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
