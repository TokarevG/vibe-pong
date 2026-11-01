import math
import typing

import pytest

from pong.ai import AI_SETTINGS, Difficulty
from pong.game import GameEvent, Match, Mode, Player
from pong.physics import SERVE_SPEED


class _NoTouch:
    """A difficulty stand-in that fails on any use, to prove Match does not read it."""

    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"difficulty was read via {name!r}")

    def __bool__(self) -> bool:
        raise AssertionError("difficulty was used as a bool")


def new_match() -> Match:
    return Match(Mode.TWO_PLAYER, Difficulty.MEDIUM)


def test_mode_has_single_player_and_two_player():
    assert {member.name for member in Mode} == {"SINGLE_PLAYER", "TWO_PLAYER"}


def test_match_stores_mode_and_difficulty_as_given():
    match = Match(Mode.SINGLE_PLAYER, Difficulty.HARD)
    assert match.mode is Mode.SINGLE_PLAYER
    assert match.difficulty is Difficulty.HARD


def test_match_difficulty_is_annotated_as_difficulty():
    hints = typing.get_type_hints(Match.__init__)
    assert hints["difficulty"] is Difficulty


def test_two_player_match_does_not_read_difficulty():
    difficulty = typing.cast(Difficulty, _NoTouch())
    match = Match(Mode.TWO_PLAYER, difficulty)
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


DT = 0.02


def run(match: Match, seconds: float, p1: int = 0, p2: int = 0) -> list[GameEvent]:
    """Call ``update`` in steps of ``DT`` for ``seconds`` and collect the events."""
    events: list[GameEvent] = []
    for _ in range(round(seconds / DT)):
        events.extend(match.update(DT, p1, p2))
    return events


def rally_match() -> Match:
    """A match that is rallying, with the ball at mid-height and no paddle in its path."""
    match = new_match()
    match.start_rally()
    return match


def test_game_event_has_the_four_members():
    assert {member.name for member in GameEvent} == {
        "PADDLE_HIT",
        "WALL_BOUNCE",
        "SCORE",
        "VICTORY",
    }


def test_p1_speed_is_default_420_in_both_modes():
    assert new_match().p1.speed == 420.0
    assert Match(Mode.SINGLE_PLAYER, Difficulty.EASY).p1.speed == 420.0


def test_two_player_p2_speed_is_default_420():
    assert new_match().p2.speed == 420.0


def test_single_player_p2_speed_is_ai_max_speed_for_each_difficulty():
    for difficulty in Difficulty:
        match = Match(Mode.SINGLE_PLAYER, difficulty)
        assert match.p2.speed == AI_SETTINGS[difficulty].max_speed


def test_single_player_p2_speed_values_from_the_table():
    assert Match(Mode.SINGLE_PLAYER, Difficulty.EASY).p2.speed == 240.0
    assert Match(Mode.SINGLE_PLAYER, Difficulty.MEDIUM).p2.speed == 330.0
    assert Match(Mode.SINGLE_PLAYER, Difficulty.HARD).p2.speed == 420.0


def test_two_player_p2_speed_ignores_difficulty():
    assert Match(Mode.TWO_PLAYER, Difficulty.EASY).p2.speed == 420.0


def test_update_moves_p1_and_p2_by_their_directions():
    match = new_match()
    events = match.update(0.1, 1, -1)
    assert match.p1.y == 250 + 420 * 0.1
    assert match.p2.y == 250 - 420 * 0.1
    assert match.p1.velocity == 420.0
    assert match.p2.velocity == -420.0
    assert events == []


def test_update_with_direction_zero_holds_paddles_still():
    match = new_match()
    match.update(0.1, 0, 0)
    assert (match.p1.y, match.p2.y) == (250, 250)


def test_serving_moves_paddles_but_not_the_ball():
    match = new_match()
    events = match.update(0.1, 1, 1)
    assert match.p1.y == 250 + 42
    assert match.p2.y == 250 + 42
    assert (match.ball.x, match.ball.y) == (500, 300)
    assert (match.ball.vx, match.ball.vy) == (0, 0)
    assert events == []


def test_serving_has_no_points_and_no_collisions():
    match = new_match()
    match.p1.y = 250
    events = run(match, 2.0, p1=0, p2=0)
    assert events == []
    assert match.score.points(Player.P1) == 0
    assert match.score.points(Player.P2) == 0
    assert match.serving is True


def test_miss_p1_holds_still_ball_goes_off_right_edge_and_p1_scores():
    match = rally_match()
    # Ball heads right at mid-high height, clear of both paddles (y 250..350).
    match.ball.x = 500.0
    match.ball.y = 50.0
    match.ball.vx = SERVE_SPEED
    match.ball.vy = 0.0
    events = run(match, 3.0, p1=0, p2=0)

    assert events == [GameEvent.SCORE]
    assert match.score.points(Player.P1) == 1
    assert match.score.points(Player.P2) == 0
    assert (match.ball.x, match.ball.y) == (500, 300)
    assert (match.ball.vx, match.ball.vy) == (0, 0)
    assert match.serving is True


def test_after_miss_the_next_serve_goes_toward_p2():
    match = rally_match()
    match.ball.x = 500.0
    match.ball.y = 50.0
    match.ball.vx = SERVE_SPEED
    run(match, 3.0)
    match.start_rally()
    assert match.ball.vx > 0
    assert match.serving is False


def test_p1_return_sets_speed_to_315_from_300():
    match = rally_match()
    # Ball at 300 px/s heading left at mid-height, with its centre inside P1's paddle.
    match.ball.x = 45.0
    match.ball.y = 300.0
    assert match.ball.vx == -SERVE_SPEED
    events = match.update(DT, 0, 0)

    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.vx > 0
    assert match.ball.vx == 315.0
    assert match.ball.vy == 0.0
    assert math.hypot(match.ball.vx, match.ball.vy) == 315.0


def test_p2_return_sends_ball_left_at_the_next_speed():
    match = rally_match()
    match.ball.x = 955.0
    match.ball.y = 300.0
    match.ball.vx = SERVE_SPEED
    events = match.update(DT, 0, 0)

    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.vx == -315.0
    assert match.ball.vy == 0.0


def test_paddle_hit_pushes_ball_out_to_the_near_face_and_keeps_y():
    match = rally_match()
    match.ball.x = 45.0
    match.ball.y = 300.0
    match.update(DT, 0, 0)
    # The step moves the ball to x 39, then the hit pushes it to P1's right face (30 + 12 + 8).
    assert match.ball.x == pytest.approx(50.0)
    assert match.ball.y == pytest.approx(300.0)


def test_ball_is_not_hit_again_by_the_same_paddle_on_the_next_step():
    match = rally_match()
    match.ball.x = 45.0
    match.ball.y = 300.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]
    assert match.update(DT, 0, 0) == []


def test_ball_far_from_a_paddle_is_not_a_hit_and_adds_no_event():
    match = rally_match()
    match.ball.x = 200.0
    match.ball.y = 50.0
    match.ball.vx = -SERVE_SPEED
    before = (match.ball.vx, match.ball.vy)
    events = match.update(DT, 0, 0)
    assert events == []
    assert (match.ball.vx, match.ball.vy) == before


def test_ball_moving_toward_a_far_paddle_is_not_a_hit():
    match = rally_match()
    # Heading toward P1 but far from it in x: a single step cannot reach it.
    match.ball.x = 500.0
    match.ball.y = 300.0
    events = match.update(DT, 0, 0)
    assert events == []
    assert match.ball.vx == -SERVE_SPEED


def test_wall_bounce_adds_wall_bounce_event():
    match = rally_match()
    match.ball.x = 500.0
    match.ball.y = 9.0
    match.ball.vx = 0.0
    match.ball.vy = -300.0
    events = match.update(DT, 0, 0)
    assert events == [GameEvent.WALL_BOUNCE]
    assert match.ball.vy > 0


def test_point_for_p2_when_ball_leaves_left_edge():
    match = rally_match()
    match.ball.x = 5.0
    match.ball.y = 50.0
    match.ball.vx = -SERVE_SPEED
    events = match.update(DT, 0, 0)
    assert events == [GameEvent.SCORE]
    assert match.score.points(Player.P2) == 1
    assert match.serving is True


def test_no_event_when_ball_centre_is_exactly_on_an_edge():
    match = rally_match()
    match.ball.x = 1000.0
    match.ball.y = 50.0
    match.ball.vx = 0.0
    assert match.update(DT, 0, 0) == []
    assert match.score.points(Player.P1) == 0


def test_victory_is_added_in_the_same_call_as_the_winning_point():
    match = rally_match()
    for _ in range(10):
        match.score.award(Player.P1)
    match.ball.x = 500.0
    match.ball.y = 50.0
    match.ball.vx = SERVE_SPEED
    events = run(match, 3.0)
    assert events == [GameEvent.SCORE, GameEvent.VICTORY]
    assert match.score.winner() is Player.P1


def test_after_victory_update_returns_empty_and_changes_nothing():
    match = rally_match()
    for _ in range(11):
        match.score.award(Player.P1)
    match.ball.x = 500.0
    match.ball.y = 300.0
    match.ball.vx = 200.0
    match.ball.vy = 50.0
    p1_before = match.p1.y
    p2_before = match.p2.y
    events = match.update(0.1, 1, 1)
    assert events == []
    assert (match.p1.y, match.p2.y) == (p1_before, p2_before)
    assert (match.ball.x, match.ball.y) == (500, 300)
    assert (match.ball.vx, match.ball.vy) == (200, 50)
    assert match.score.points(Player.P1) == 11


def test_dt_zero_changes_no_positions():
    match = rally_match()
    match.ball.x = 500.0
    match.ball.y = 300.0
    match.ball.vx = 200.0
    match.ball.vy = 100.0
    match.update(0.0, 1, -1)
    assert (match.p1.y, match.p2.y) == (250, 250)
    assert (match.ball.x, match.ball.y) == (500, 300)


def test_fast_ball_inside_p1_window_is_hit_in_one_step():
    # Scripted case from #13: the ball centre starts inside P1 and leaves it in one step.
    match = rally_match()
    match.ball.x = 36.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    events = match.update(DT, 0, 0)
    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.vx > 0


def test_ball_starting_inside_window_and_passing_through_is_hit():
    # Starts inside P1's reach, ends past it at x 18: only the start sample touches.
    match = rally_match()
    match.ball.x = 36.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]


def test_ball_crossing_paddle_inside_one_long_step_is_hit():
    # A longer step than the loop allows, so neither end lies within P1's reach.
    # Only a sample between the ends touches the paddle.
    match = rally_match()
    match.ball.x = 100.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    events = match.update(0.1, 0, 0)
    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.vx > 0


def test_ball_moving_away_from_p1_inside_window_is_not_hit():
    match = rally_match()
    match.ball.x = 36.0
    match.ball.y = 300.0
    match.ball.vx = 900.0
    events = match.update(DT, 0, 0)
    assert events == []
    assert match.ball.vx == 900.0


def test_qa_repro_x50_at_vx_minus_700_is_hit():
    match = rally_match()
    match.ball.x = 50.0
    match.ball.y = 300.0
    match.ball.vx = -700.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]


def test_qa_repro_x50_at_vx_minus_900_is_hit():
    match = rally_match()
    match.ball.x = 50.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]


def test_qa_repro_shallow_graze_on_p1_corner_is_hit():
    # QA repro: the path only clips P1's rounded top-left corner by 0.15 px, which
    # the old fixed samples missed. The exact segment test must count it.
    match = rally_match()
    match.ball.x = 34.4043
    match.ball.y = 241.1766
    match.ball.vx = -741.41
    match.ball.vy = 140.44
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]
    assert match.ball.vx > 0


def test_p1_hit_pushes_ball_to_the_right_face_at_x_50():
    # Scripted case from #13: the ball's centre ends at x 50 (30 + 12 + 8), moving at +900.
    match = rally_match()
    match.ball.x = 36.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    events = match.update(DT, 0, 0)
    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.x == pytest.approx(50.0)
    assert match.ball.y == pytest.approx(300.0)
    assert match.ball.vx == pytest.approx(900.0)
    assert match.ball.vy == pytest.approx(0.0)


def test_p2_hit_pushes_ball_to_the_left_face_and_sends_it_left():
    # Mirror of the P1 case: P2 at x 958, centre 964, so the ball's left face is 958 - 8 = 950.
    match = rally_match()
    match.ball.x = 944.0
    match.ball.y = 300.0
    match.ball.vx = 900.0
    events = match.update(DT, 0, 0)
    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.x == pytest.approx(950.0)
    assert match.ball.y == pytest.approx(300.0)
    assert match.ball.vx == pytest.approx(-900.0)


def test_p2_hit_at_exact_centre_x_goes_to_the_left_face_regression():
    # Regression: P2 at x 958 has its centre at 964. The ball is at exactly 964 and
    # moves right at 900 px/s, so it ends at 982. It came from the left, so it must be
    # pushed to the left face (958 - 8 = 950), not the right face.
    match = rally_match()
    match.ball.x = 964.0
    match.ball.y = 300.0
    match.ball.vx = 900.0
    events = match.update(DT, 0, 0)
    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.x == pytest.approx(950.0)
    assert match.ball.y == pytest.approx(300.0)
    assert match.ball.vx == pytest.approx(-900.0)


def test_p2_hit_at_exact_centre_x_slow_ball_goes_to_the_left_face():
    # Same tie at a slower speed: the ball ends at 970, still on the left-face side.
    match = rally_match()
    match.ball.x = 964.0
    match.ball.y = 300.0
    match.ball.vx = 300.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]
    assert match.ball.x == pytest.approx(950.0)
    assert match.ball.vx < 0


def test_p1_hit_at_exact_centre_x_goes_to_the_right_face():
    # P1 at x 30 has its centre at 36. The ball starts at exactly 36 moving left.
    match = rally_match()
    match.ball.x = 36.0
    match.ball.y = 300.0
    match.ball.vx = -300.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]
    assert match.ball.x == pytest.approx(50.0)
    assert match.ball.vx > 0


def test_p1_hit_from_right_with_centre_left_of_midline_goes_to_right_face():
    # The ball starts left of P1's centre x (36) but is moving left, so it came from
    # the right. It must go to the right face (50), not the left face.
    match = rally_match()
    match.ball.x = 33.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    assert match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]
    assert match.ball.x == pytest.approx(50.0)
    assert match.ball.vx == pytest.approx(900.0)


def test_p2_ball_already_clear_of_the_left_face_is_not_moved():
    # At dt 0 the ball stays at 950, which is one radius clear of P2's left face
    # (958 - 8). It still touches the paddle, so it is a hit, and the push leaves it.
    match = rally_match()
    match.ball.x = 950.0
    match.ball.y = 300.0
    match.ball.vx = 900.0
    assert match.update(0.0, 0, 0) == [GameEvent.PADDLE_HIT]
    assert match.ball.x == 950.0
    assert match.ball.y == 300.0
    assert match.ball.vx == pytest.approx(-900.0)


def test_ball_already_one_radius_clear_of_the_face_is_not_moved():
    # At dt 0 the ball stays where it is: centre x 50 is already one radius clear of
    # P1's right face (42 + 8), and it still touches the paddle's corner, so it is a hit.
    # The push must leave it at 50.
    match = rally_match()
    match.ball.x = 50.0
    match.ball.y = 300.0
    match.ball.vx = -900.0
    events = match.update(0.0, 0, 0)
    assert events == [GameEvent.PADDLE_HIT]
    assert match.ball.x == 50.0
    assert match.ball.y == 300.0


def test_ball_is_never_left_behind_the_paddle_on_the_near_side():
    # Starts on the side the ball approaches from (not past the paddle's centre on its
    # far side). After any hit, the ball must be on the far side of the face, moving away.
    hits = 0
    for x0 in [36.0 + i for i in range(30)]:
        for vx0 in (-300.0, -700.0, -900.0):
            for y0 in (260.0, 300.0, 340.0):
                match = rally_match()
                match.ball.x = x0
                match.ball.y = y0
                match.ball.vx = vx0
                if match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]:
                    hits += 1
                    assert match.ball.x >= 30 + 12 + 8 - 1e-9, (x0, vx0, y0)
                    assert match.ball.vx > 0, (x0, vx0, y0)
    assert hits > 0


def test_ball_is_never_left_behind_p2_on_the_near_side():
    # Mirror of the P1 sweep: the ball approaches P2 from the left (x below 964). Each
    # hit must go to P2's left face, which is the face it came from.
    hits = 0
    for x0 in [944.0 + i for i in range(20)]:
        for vx0 in (300.0, 700.0, 900.0):
            for y0 in (260.0, 300.0, 340.0):
                match = rally_match()
                match.ball.x = x0
                match.ball.y = y0
                match.ball.vx = vx0
                if match.update(DT, 0, 0) == [GameEvent.PADDLE_HIT]:
                    hits += 1
                    assert match.ball.x <= 958 - 8 + 1e-9, (x0, vx0, y0)
                    assert match.ball.vx < 0, (x0, vx0, y0)
    assert hits > 0
