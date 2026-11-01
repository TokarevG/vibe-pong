from pong.game import Match, Mode, Player
from pong.physics import SERVE_SPEED


class _NoTouch:
    """A difficulty stand-in that fails on any use, to prove Match does not read it."""

    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"difficulty was read via {name!r}")

    def __bool__(self) -> bool:
        raise AssertionError("difficulty was used as a bool")


def new_match() -> Match:
    return Match(Mode.TWO_PLAYER, None)


def test_mode_has_single_player_and_two_player():
    assert {member.name for member in Mode} == {"SINGLE_PLAYER", "TWO_PLAYER"}


def test_match_stores_mode_and_difficulty_as_given():
    difficulty = object()
    match = Match(Mode.SINGLE_PLAYER, difficulty)
    assert match.mode is Mode.SINGLE_PLAYER
    assert match.difficulty is difficulty


def test_match_does_not_read_difficulty():
    difficulty = _NoTouch()
    match = Match(Mode.SINGLE_PLAYER, difficulty)
    assert match.difficulty is difficulty


def test_p1_paddle_is_at_x30_y250_and_100_by_12():
    paddle = new_match().p1
    assert (paddle.x, paddle.y) == (30, 250)
    assert (paddle.width, paddle.height) == (12, 100)


def test_p2_paddle_is_at_x958_so_right_edge_is_970():
    paddle = new_match().p2
    assert (paddle.x, paddle.y) == (958, 250)
    assert (paddle.width, paddle.height) == (12, 100)
    assert paddle.x + paddle.width == 970


def test_new_match_score_is_zero_to_zero():
    score = new_match().score
    assert score.points(Player.P1) == 0
    assert score.points(Player.P2) == 0


def test_new_match_ball_is_centred_and_still_with_radius_8():
    ball = new_match().ball
    assert (ball.x, ball.y) == (500, 300)
    assert ball.vx == 0
    assert ball.vy == 0
    assert ball.radius == 8


def test_new_match_starts_serving():
    assert new_match().serving is True


def test_start_rally_does_nothing_when_not_serving():
    match = new_match()
    match.start_rally()
    match.ball.vx = 123.0
    match.ball.vy = 45.0
    match.start_rally()
    assert match.ball.vx == 123.0
    assert match.ball.vy == 45.0
    assert match.serving is False


def test_start_rally_while_serving_leaves_serving_state():
    match = new_match()
    match.start_rally()
    assert match.serving is False


def test_start_rally_sets_serve_speed_and_zero_vertical_velocity():
    match = new_match()
    match.start_rally()
    assert abs(match.ball.vx) == SERVE_SPEED == 300
    assert match.ball.vy == 0


def test_first_serve_goes_toward_p1_on_the_left():
    match = new_match()
    match.start_rally()
    assert match.ball.vx < 0


def test_end_rally_p2_scores_one_point_for_p2():
    match = new_match()
    match.start_rally()
    match.end_rally(Player.P2)
    assert match.score.points(Player.P2) == 1
    assert match.score.points(Player.P1) == 0


def test_end_rally_centres_ball_with_zero_velocity():
    match = new_match()
    match.start_rally()
    match.ball.x = 100.0
    match.ball.y = 50.0
    match.end_rally(Player.P1)
    assert (match.ball.x, match.ball.y) == (500, 300)
    assert match.ball.vx == 0
    assert match.ball.vy == 0


def test_end_rally_enters_serving_state():
    match = new_match()
    match.start_rally()
    match.end_rally(Player.P1)
    assert match.serving is True


def test_serve_after_p2_scores_goes_toward_p1():
    match = new_match()
    match.start_rally()
    match.end_rally(Player.P2)
    match.start_rally()
    assert match.ball.vx < 0
    assert match.ball.vy == 0
    assert abs(match.ball.vx) == SERVE_SPEED


def test_serve_after_p1_scores_goes_toward_p2():
    match = new_match()
    match.start_rally()
    match.end_rally(Player.P1)
    match.start_rally()
    assert match.ball.vx > 0
    assert match.ball.vy == 0
    assert abs(match.ball.vx) == SERVE_SPEED


def test_serve_direction_follows_the_most_recent_point():
    match = new_match()
    match.start_rally()
    match.end_rally(Player.P1)
    match.start_rally()
    match.end_rally(Player.P1)
    match.start_rally()
    assert match.ball.vx > 0


def test_ball_stays_still_while_serving_after_end_rally():
    match = new_match()
    match.start_rally()
    match.end_rally(Player.P2)
    assert match.ball.vx == 0
    assert match.ball.vy == 0


def test_start_rally_does_nothing_once_a_player_has_won():
    match = new_match()
    for _ in range(11):
        match.score.award(Player.P1)
    assert match.score.winner() is Player.P1
    match.start_rally()
    assert match.serving is True
    assert match.ball.vx == 0
    assert match.ball.vy == 0


def test_start_rally_does_nothing_for_p2_win_too():
    match = new_match()
    for _ in range(11):
        match.score.award(Player.P2)
    match.start_rally()
    assert match.serving is True
    assert match.ball.vx == 0
