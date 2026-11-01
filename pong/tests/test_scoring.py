import ast
from pathlib import Path

from pong.game import Player, scorer

GAME_SOURCE = Path(__file__).parent.parent / "game.py"
WIDTH = 1000


def test_player_enum_has_p1_and_p2():
    assert {member.name for member in Player} == {"P1", "P2"}


def test_module_does_not_import_pygame():
    tree = ast.parse(GAME_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "pygame" for name in imported)


def test_ball_inside_field_scores_nothing():
    assert scorer(500, WIDTH) is None


def test_ball_past_left_edge_scores_for_p2():
    assert scorer(-1, WIDTH) is Player.P2


def test_ball_past_right_edge_scores_for_p1():
    assert scorer(WIDTH + 1, WIDTH) is Player.P1


def test_ball_centre_exactly_on_left_edge_scores_nothing():
    assert scorer(0, WIDTH) is None


def test_ball_centre_exactly_on_right_edge_scores_nothing():
    assert scorer(WIDTH, WIDTH) is None


def test_left_exit_scores_for_p2_not_p1():
    assert scorer(-50.5, WIDTH) is Player.P2


def test_right_exit_scores_for_p1_not_p2():
    assert scorer(WIDTH + 50.5, WIDTH) is Player.P1
