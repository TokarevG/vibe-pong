import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.__main__ import (
    GAME_OVER_ITEMS,
    GameOverItem,
    GameOverOutcome,
    GameOverScreen,
    MenuAction,
)
from pong.ai import AIController, Difficulty
from pong.game import WINNING_SCORE, Match, Mode, Player
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH
from pong.settings import Settings, config_path, default_settings, save_settings

pygame = main_module.pygame

DOWN = MenuAction.DOWN
UP = MenuAction.UP
ENTER = MenuAction.ENTER
BACK = MenuAction.BACK
LEFT = MenuAction.LEFT
RIGHT = MenuAction.RIGHT


@pytest.fixture(autouse=True)
def pygame_session():
    # Each test starts and stops pygame, so a test that calls main() cannot
    # leave the others without a display or fonts.
    pygame.init()
    main_module._menu_font.cache_clear()
    main_module._digit_font.cache_clear()
    yield
    main_module._menu_font.cache_clear()
    main_module._digit_font.cache_clear()
    pygame.quit()


@pytest.fixture
def config_home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def _finished_match(
    mode: Mode = Mode.TWO_PLAYER,
    winner: Player = Player.P1,
    loser_points: int = 7,
) -> Match:
    """Return a match that ``winner`` has won, ``WINNING_SCORE`` to ``loser_points``."""
    loser = Player.P2 if winner is Player.P1 else Player.P1
    match = Match(mode, Difficulty.MEDIUM)
    for _ in range(loser_points):
        match.end_rally(loser)
    for _ in range(WINNING_SCORE):
        match.end_rally(winner)
    return match


def _one_point_from_victory(match: Match) -> Match:
    """Put ``match`` one point from the end: P1 has 10, P2 has 6, and the ball is leaving.

    The ball starts past P1's edge, so the next update scores for P1 in any frame
    length, and the match is won.
    """
    for _ in range(6):
        match.end_rally(Player.P2)
    for _ in range(WINNING_SCORE - 1):
        match.end_rally(Player.P1)
    match.start_rally()
    match.ball.x = PLAYFIELD_WIDTH + 0.5
    match.ball.vx = 1000.0
    match.ball.vy = 0.0
    return match


def _surface() -> pygame.Surface:
    return pygame.Surface((PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT))


def _highlight(screen: GameOverScreen, item: GameOverItem) -> None:
    while screen.selected is not item:
        screen.handle(DOWN)


# The screen's state and keys


def test_items_are_rematch_main_menu_quit_in_order():
    assert list(GAME_OVER_ITEMS) == [
        GameOverItem.REMATCH,
        GameOverItem.MAIN_MENU,
        GameOverItem.QUIT,
    ]
    assert GameOverScreen(_finished_match()).lines() == [
        "Rematch",
        "Main Menu",
        "Quit",
    ]


def test_highlight_starts_on_rematch():
    assert GameOverScreen(_finished_match()).selected is GameOverItem.REMATCH


def test_down_moves_highlight_and_wraps_from_last_to_first():
    screen = GameOverScreen(_finished_match())
    assert screen.handle(DOWN) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.MAIN_MENU
    assert screen.handle(DOWN) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.QUIT
    assert screen.handle(DOWN) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.REMATCH


def test_up_wraps_from_first_to_last_and_back():
    screen = GameOverScreen(_finished_match())
    assert screen.handle(UP) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.QUIT
    assert screen.handle(UP) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.MAIN_MENU
    assert screen.handle(UP) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.REMATCH


def test_moving_the_highlight_does_not_activate_the_row():
    screen = GameOverScreen(_finished_match())
    assert screen.handle(DOWN) is GameOverOutcome.NONE
    assert screen.handle(UP) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.REMATCH


@pytest.mark.parametrize(
    ("item", "outcome"),
    [
        (GameOverItem.REMATCH, GameOverOutcome.REMATCH),
        (GameOverItem.MAIN_MENU, GameOverOutcome.MAIN_MENU),
        (GameOverItem.QUIT, GameOverOutcome.QUIT),
    ],
)
def test_enter_activates_the_highlighted_row(item: GameOverItem, outcome):
    screen = GameOverScreen(_finished_match())
    _highlight(screen, item)
    assert screen.handle(ENTER) is outcome


def test_arrow_and_enter_keys_drive_the_screen():
    screen = GameOverScreen(_finished_match())
    assert (
        main_module._handle_game_over_key(pygame.K_DOWN, screen) is GameOverOutcome.NONE
    )
    assert screen.selected is GameOverItem.MAIN_MENU
    assert (
        main_module._handle_game_over_key(pygame.K_UP, screen) is GameOverOutcome.NONE
    )
    assert screen.selected is GameOverItem.REMATCH
    assert (
        main_module._handle_game_over_key(pygame.K_RETURN, screen)
        is GameOverOutcome.REMATCH
    )


@pytest.mark.parametrize(
    "key",
    [
        pygame.K_ESCAPE,
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_w,
        pygame.K_s,
        pygame.K_SPACE,
    ],
)
def test_other_keys_do_nothing_on_the_game_over_screen(key: int):
    screen = GameOverScreen(_finished_match())
    _highlight(screen, GameOverItem.MAIN_MENU)
    assert main_module._handle_game_over_key(key, screen) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.MAIN_MENU


def test_esc_does_nothing_even_on_a_highlighted_row():
    screen = GameOverScreen(_finished_match())
    assert screen.handle(BACK) is GameOverOutcome.NONE
    assert screen.handle(LEFT) is GameOverOutcome.NONE
    assert screen.handle(RIGHT) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.REMATCH


def test_navigation_ignores_the_paddle_bindings():
    # Rebind P1 to the arrows' neighbours. The screen still answers to the arrows
    # and Enter, and the paddle keys do nothing on it.
    settings = default_settings()
    settings.bindings["p1_up"] = "i"
    settings.bindings["p1_down"] = "k"
    screen = GameOverScreen(_finished_match())
    assert main_module._handle_game_over_key(pygame.K_k, screen) is GameOverOutcome.NONE
    assert screen.selected is GameOverItem.REMATCH


def test_screen_needs_a_match_with_a_winner():
    with pytest.raises(ValueError):
        GameOverScreen(Match(Mode.TWO_PLAYER, Difficulty.MEDIUM))


# The winner, the final score and the labels


def test_winner_line_names_player_1_when_player_1_wins():
    screen = GameOverScreen(_finished_match(winner=Player.P1))
    assert screen.winner_text() == "Player 1 wins"


def test_winner_line_names_player_2_in_two_player():
    screen = GameOverScreen(
        _finished_match(mode=Mode.TWO_PLAYER, winner=Player.P2, loser_points=9)
    )
    assert screen.winner_text() == "Player 2 wins"


def test_winner_line_names_the_computer_when_it_wins_in_single_player():
    screen = GameOverScreen(
        _finished_match(mode=Mode.SINGLE_PLAYER, winner=Player.P2, loser_points=9)
    )
    assert screen.winner_text() == "Computer wins"


def test_final_score_is_shown_with_an_en_dash_in_player_order():
    screen = GameOverScreen(_finished_match(winner=Player.P1, loser_points=7))
    assert screen.score_text() == "11 – 7"


def test_final_score_keeps_player_1_on_the_left_when_player_2_wins():
    screen = GameOverScreen(_finished_match(winner=Player.P2, loser_points=9))
    assert screen.score_text() == "9 – 11"


def test_single_player_labels_the_right_paddle_computer():
    screen = GameOverScreen(_finished_match(mode=Mode.SINGLE_PLAYER))
    assert screen.label(Player.P1) == "Player 1"
    assert screen.label(Player.P2) == "Computer"


def test_two_player_labels_both_paddles_by_player():
    screen = GameOverScreen(_finished_match(mode=Mode.TWO_PLAYER))
    assert screen.label(Player.P1) == "Player 1"
    assert screen.label(Player.P2) == "Player 2"


def test_screen_copies_the_score_when_it_is_built():
    match = _finished_match(winner=Player.P1, loser_points=7)
    screen = GameOverScreen(match)
    match.restart()
    assert screen.score_text() == "11 – 7"
    assert screen.winner_text() == "Player 1 wins"


# The game-over screen drawn over a surface


def _pixels(surface: pygame.Surface) -> bytes:
    return pygame.image.tobytes(surface, "RGB")


def test_draw_game_over_draws_text_on_a_black_background():
    surface = _surface()
    main_module.draw_game_over(surface, GameOverScreen(_finished_match()))
    assert _pixels(surface) != _pixels(
        pygame.Surface((PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT))
    )


def test_draw_game_over_replaces_the_match_view():
    # The match's P1 paddle is white in a normal frame. On the game-over screen
    # that spot is black, because the match is not drawn at all.
    match = _finished_match()
    paddle_x = round(match.p1.x + match.p1.width / 2)
    paddle_y = round(match.p1.y + match.p1.height / 2)
    frame = _surface()
    main_module.draw_frame(frame, match)
    assert tuple(frame.get_at((paddle_x, paddle_y)))[:3] == (255, 255, 255)

    surface = _surface()
    main_module.draw_game_over(surface, GameOverScreen(match))
    assert tuple(surface.get_at((paddle_x, paddle_y)))[:3] == (0, 0, 0)


def test_draw_game_over_highlight_changes_the_drawing():
    rematch_first = _surface()
    main_module.draw_game_over(rematch_first, GameOverScreen(_finished_match()))

    quit_highlighted = _surface()
    screen = GameOverScreen(_finished_match())
    _highlight(screen, GameOverItem.QUIT)
    main_module.draw_game_over(quit_highlighted, screen)

    assert _pixels(rematch_first) != _pixels(quit_highlighted)


def test_draw_game_over_labels_differ_between_single_and_two_player():
    single = _surface()
    main_module.draw_game_over(
        single, GameOverScreen(_finished_match(mode=Mode.SINGLE_PLAYER))
    )
    two = _surface()
    main_module.draw_game_over(
        two, GameOverScreen(_finished_match(mode=Mode.TWO_PLAYER))
    )
    assert _pixels(single) != _pixels(two)


def test_draw_game_over_does_nothing_for_zero_size():
    surface = pygame.Surface((0, 0))
    main_module.draw_game_over(surface, GameOverScreen(_finished_match()))
    assert surface.get_size() == (0, 0)


# The real loop, driven by scripted events


def _key(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


class _Held:
    """Stands in for ``pygame.key.get_pressed()`` with W and Up held."""

    def __getitem__(self, key_code: int) -> bool:
        return key_code in (pygame.K_w, pygame.K_UP)


class _Loop:
    """What the scripted run recorded: draws in order, and the matches and AIs made."""

    def __init__(self) -> None:
        self.draws: list[str] = []
        self.game_overs: list[GameOverScreen] = []
        self.matches: list[Match] = []
        self.ais: list[AIController] = []
        self.restarts = 0
        self.victory_sounds = 0
        self.p1_y_on_game_over: list[float] = []
        self.remaining: list[list[pygame.event.Event]] = []


def _script(
    monkeypatch,
    frames: list[list[pygame.event.Event]],
    *,
    prepare: bool = True,
    held: bool = False,
) -> _Loop:
    """Drive ``main()`` with ``frames`` of events, then QUIT forever, and record it.

    With ``prepare`` the first match is one point from victory. Each match is built
    by the real ``_start_match`` and then prepared, so Rematch and the menus use the
    real code.
    """
    loop = _Loop()
    queue = list(frames)
    loop.remaining = queue

    def fake_get(*args, **kwargs):
        if queue:
            return queue.pop(0)
        return [pygame.event.Event(pygame.QUIT)]

    real_start = main_module._start_match
    real_restart = main_module._restart_match
    real_draw_frame = main_module.draw_frame
    real_draw_menu = main_module.draw_menu
    real_draw_pause = main_module.draw_pause_menu
    real_draw_game_over = main_module.draw_game_over
    real_play = main_module.SoundPlayer.play

    def start(settings: Settings):
        match, ai = real_start(settings)
        if prepare:
            _one_point_from_victory(match)
        loop.matches.append(match)
        loop.ais.append(ai)
        return match, ai

    def restart(match: Match, settings: Settings):
        loop.restarts += 1
        return real_restart(match, settings)

    def draw_frame(surface, match):
        loop.draws.append("frame")
        real_draw_frame(surface, match)

    def draw_menu(surface, menu):
        loop.draws.append("menu")
        real_draw_menu(surface, menu)

    def draw_pause(surface, pause):
        loop.draws.append("pause")
        real_draw_pause(surface, pause)

    def draw_over(surface, screen):
        loop.draws.append("game_over")
        loop.game_overs.append(screen)
        loop.p1_y_on_game_over.append(loop.matches[-1].p1.y)
        real_draw_game_over(surface, screen)

    def play(self, events, settings):
        loop.victory_sounds += events.count(main_module.GameEvent.VICTORY)
        real_play(self, events, settings)

    monkeypatch.setattr(pygame.event, "get", fake_get)
    monkeypatch.setattr(main_module, "_start_match", start)
    monkeypatch.setattr(main_module, "_restart_match", restart)
    monkeypatch.setattr(main_module, "draw_frame", draw_frame)
    monkeypatch.setattr(main_module, "draw_menu", draw_menu)
    monkeypatch.setattr(main_module, "draw_pause_menu", draw_pause)
    monkeypatch.setattr(main_module, "draw_game_over", draw_over)
    monkeypatch.setattr(main_module.SoundPlayer, "play", play)
    if held:
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Held())
    return loop


def _two_player_settings() -> None:
    settings = Settings(mode=Mode.TWO_PLAYER, difficulty=Difficulty.HARD)
    save_settings(config_path(os.environ, Path.home()), settings)


def test_winning_the_match_shows_the_game_over_screen_in_place_of_the_match(
    config_home, monkeypatch
):
    loop = _script(monkeypatch, [[_key(pygame.K_RETURN)], [], []])
    assert main_module.main() == 0
    # The match is won on the first frame, and from then on only the game-over
    # screen is drawn, never the match.
    assert loop.draws[0] == "game_over"
    assert set(loop.draws) == {"game_over"}
    assert len(loop.game_overs) == len(loop.draws)


def test_victory_sound_plays_once_when_the_screen_appears(config_home, monkeypatch):
    loop = _script(
        monkeypatch,
        [[_key(pygame.K_RETURN)], [], [], [], []],
    )
    assert main_module.main() == 0
    assert loop.draws.count("game_over") >= 4
    assert loop.victory_sounds == 1


def test_game_over_screen_shows_the_winner_and_score_from_the_match(
    config_home, monkeypatch
):
    loop = _script(monkeypatch, [[_key(pygame.K_RETURN)], []])
    assert main_module.main() == 0
    screen = loop.game_overs[0]
    assert screen.winner_text() == "Player 1 wins"
    assert screen.score_text() == "11 – 6"


def test_two_player_game_over_labels_both_sides(config_home, monkeypatch):
    _two_player_settings()
    loop = _script(monkeypatch, [[_key(pygame.K_RETURN)], []])
    assert main_module.main() == 0
    screen = loop.game_overs[0]
    assert screen.winner_text() == "Player 1 wins"
    assert screen.label(Player.P1) == "Player 1"
    assert screen.label(Player.P2) == "Player 2"


def test_rematch_starts_a_new_serving_match_with_the_same_mode_and_difficulty(
    config_home, monkeypatch
):
    _two_player_settings()
    loop = _script(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game, which is won at once
            [_key(pygame.K_RETURN)],  # Rematch is highlighted
            [],
        ],
    )
    assert main_module.main() == 0
    assert len(loop.matches) == 1
    match = loop.matches[0]
    assert loop.restarts == 1
    assert match.mode is Mode.TWO_PLAYER
    assert match.difficulty is Difficulty.HARD
    assert match.serving
    assert match.score.points(Player.P1) == 0
    assert match.score.points(Player.P2) == 0
    assert match.score.winner() is None
    # The match is shown again, not the game-over screen.
    assert loop.draws[-1] == "frame"


def test_rematch_makes_a_new_ai_controller(config_home, monkeypatch):
    _two_player_settings()
    loop = _script(
        monkeypatch,
        [[_key(pygame.K_RETURN)], [_key(pygame.K_RETURN)], []],
    )
    real_restart = main_module._restart_match
    restarted: list[AIController] = []

    def record(match, settings):
        ai = real_restart(match, settings)
        restarted.append(ai)
        return ai

    monkeypatch.setattr(main_module, "_restart_match", record)
    assert main_module.main() == 0
    assert len(restarted) == 1
    assert restarted[0] is not loop.ais[0]


def test_main_menu_row_discards_the_match_and_shows_the_main_menu(
    config_home, monkeypatch
):
    loop = _script(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game, which is won at once
            [_key(pygame.K_DOWN)],  # Main Menu
            [_key(pygame.K_RETURN)],
            [],
        ],
    )
    assert main_module.main() == 0
    assert loop.restarts == 0
    assert loop.draws[-1] == "menu"
    # Only one match was ever started, so the menu did not make a new one.
    assert len(loop.matches) == 1


def test_quit_row_exits_the_program_cleanly(config_home, monkeypatch):
    loop = _script(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game, which is won at once
            [_key(pygame.K_DOWN)],
            [_key(pygame.K_DOWN)],  # Quit
            [_key(pygame.K_RETURN)],
            # Anything after Quit is never read, because the loop has ended.
            [_key(pygame.K_RETURN)],
            [_key(pygame.K_RETURN)],
        ],
    )
    assert main_module.main() == 0
    assert len(loop.remaining) == 2
    assert loop.draws[-1] == "game_over"
    assert len(loop.matches) == 1


def test_window_close_on_the_game_over_screen_exits_cleanly(config_home, monkeypatch):
    loop = _script(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],
            [pygame.event.Event(pygame.QUIT)],
            [_key(pygame.K_RETURN)],
        ],
    )
    assert main_module.main() == 0
    assert len(loop.remaining) == 1
    assert loop.draws[-1] == "game_over"


def test_paddle_rally_and_esc_keys_do_nothing_on_the_game_over_screen(
    config_home, monkeypatch
):
    loop = _script(
        monkeypatch,
        [
            [_key(pygame.K_RETURN)],  # Start Game, which is won at once
            [_key(pygame.K_w)],
            [_key(pygame.K_SPACE)],
            [_key(pygame.K_ESCAPE)],
            [_key(pygame.K_LEFT)],
            [_key(pygame.K_RIGHT)],
            [],
        ],
        held=True,
    )
    assert main_module.main() == 0
    # The screen is still up, and the match is untouched by those keys.
    assert loop.draws[-1] == "game_over"
    assert "pause" not in loop.draws
    assert loop.restarts == 0
    assert loop.game_overs[-1].selected is GameOverItem.REMATCH
    match = loop.matches[0]
    assert match.score.winner() is Player.P1
    assert match.paused is False
    # Held W and Up do not move P1 once the match is over.
    assert len(set(loop.p1_y_on_game_over)) == 1
