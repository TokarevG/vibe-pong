import ast
from pathlib import Path

from pong.game import Player, Score, scorer

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


def award_times(score: Score, player: Player, times: int) -> None:
    for _ in range(times):
        score.award(player)


def test_score_starts_at_zero_for_both_players():
    score = Score()
    assert score.points(Player.P1) == 0
    assert score.points(Player.P2) == 0


def test_award_adds_one_point_to_that_player():
    score = Score()
    score.award(Player.P1)
    assert score.points(Player.P1) == 1


def test_award_p2_adds_one_point_to_p2():
    score = Score()
    score.award(Player.P2)
    assert score.points(Player.P2) == 1


def test_award_changes_only_the_awarded_player():
    score = Score()
    award_times(score, Player.P1, 3)
    assert score.points(Player.P1) == 3
    assert score.points(Player.P2) == 0


def test_winner_is_none_at_start():
    assert Score().winner() is None


def test_winner_is_none_at_10_points():
    score = Score()
    award_times(score, Player.P1, 10)
    assert score.points(Player.P1) == 10
    assert score.winner() is None


def test_winner_is_player_at_exactly_11_points():
    score = Score()
    award_times(score, Player.P1, 11)
    assert score.winner() is Player.P1


def test_winner_is_p2_at_11_points():
    score = Score()
    award_times(score, Player.P2, 11)
    assert score.winner() is Player.P2


def test_p1_at_11_and_p2_at_10_gives_p1_and_leaves_p2_at_10():
    score = Score()
    award_times(score, Player.P1, 11)
    award_times(score, Player.P2, 10)
    assert score.winner() is Player.P1
    assert score.points(Player.P2) == 10


def test_scoring_continues_after_a_win():
    score = Score()
    award_times(score, Player.P1, 12)
    assert score.points(Player.P1) == 12
    assert score.winner() is Player.P1


def test_first_player_to_11_stays_winner_if_other_player_also_reaches_11():
    score = Score()
    award_times(score, Player.P1, 11)
    award_times(score, Player.P2, 11)
    assert score.points(Player.P2) == 11
    assert score.winner() is Player.P1
