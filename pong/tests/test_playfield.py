import ast
from pathlib import Path

import pytest

from pong.playfield import fit_playfield

PLAYFIELD_SOURCE = Path(__file__).parent.parent / "playfield.py"


def test_module_does_not_import_pygame():
    tree = ast.parse(PLAYFIELD_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "pygame" for name in imported)


def test_returns_three_floats_in_order():
    result = fit_playfield(1200, 600)
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(isinstance(value, float) for value in result)


def test_int_inputs_return_floats():
    scale, offset_x, offset_y = fit_playfield(2000, 1200)
    assert isinstance(scale, float)
    assert isinstance(offset_x, float)
    assert isinstance(offset_y, float)


def test_native_size_has_scale_one_and_no_offset():
    assert fit_playfield(1000, 600) == (1.0, 0.0, 0.0)


def test_double_size_has_scale_two_and_no_offset():
    assert fit_playfield(2000, 1200) == (2.0, 0.0, 0.0)


def test_wider_than_five_by_three_centres_horizontally():
    scale, offset_x, offset_y = fit_playfield(1200, 600)
    assert scale == 1.0
    assert offset_x == 100.0
    assert offset_y == 0.0
    assert offset_x > 0
    assert offset_y == 0


def test_taller_than_five_by_three_centres_vertically():
    scale, offset_x, offset_y = fit_playfield(1000, 800)
    assert scale == 1.0
    assert offset_x == 0.0
    assert offset_y == 100.0
    assert offset_x == 0
    assert offset_y > 0


def test_scale_is_not_rounded():
    scale, _, _ = fit_playfield(1000, 1000)
    assert scale == pytest.approx(1.0)
    scale, _, _ = fit_playfield(700, 333)
    assert scale == min(700 / 1000, 333 / 600)
    assert scale != round(scale)


def test_scaled_playfield_is_centred_in_window():
    window_w, window_h = 937, 811
    scale, offset_x, offset_y = fit_playfield(window_w, window_h)
    assert scale == min(window_w / 1000, window_h / 600)
    assert offset_x == (window_w - 1000 * scale) / 2
    assert offset_y == (window_h - 600 * scale) / 2
    assert offset_x + 1000 * scale + offset_x == pytest.approx(window_w)
    assert offset_y + 600 * scale + offset_y == pytest.approx(window_h)


@pytest.mark.parametrize(
    ("window_w", "window_h"),
    [
        (0, 600),
        (1000, 0),
        (0, 0),
        (-1, 600),
        (1000, -1),
        (-1000, -600),
        (float("nan"), 600),
        (1000, float("nan")),
    ],
)
def test_non_positive_window_size_raises_value_error(window_w, window_h):
    with pytest.raises(ValueError):
        fit_playfield(window_w, window_h)
