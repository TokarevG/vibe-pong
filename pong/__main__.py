"""Entry point: open the Pong window and run the frame loop at 60 FPS.

Run with ``python -m pong``. This is the only module that imports pygame.
"""

import functools
import os
import random
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Protocol

import pygame

from pong.ai import AIController, Difficulty
from pong.game import GameEvent, Match, Mode, Player
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH, fit_playfield
from pong.settings import (
    RESERVED_KEY,
    Settings,
    config_path,
    default_settings,
    find_binding_conflicts,
    load_settings,
    save_settings,
)

FPS = 60
# Longest step the simulation may take in one frame, so a slow frame cannot
# let the ball pass through a paddle.
MAX_DT = 0.02

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

CENTRE_LINE_X = 500.0
"""Horizontal position of the dashed centre line, in logical units."""
CENTRE_LINE_WIDTH = 4.0
DASH_LENGTH = 20.0
DASH_GAP = 20.0

SCORE_X = {Player.P1: 250.0, Player.P2: 750.0}
"""Horizontal centre of each player's score, in logical units."""
SCORE_TOP = 40.0
"""Distance from the top of the playfield to the top of the score digits."""
DIGIT_FONT_SIZE = 80
"""Font size in logical units. At this size a digit is about 40 units tall."""


@functools.lru_cache(maxsize=16)
def _digit_font(size: int) -> pygame.font.Font:
    """Return the default font at ``size`` pixels, cached by size."""
    return pygame.font.Font(None, size)


def _screen_rect(
    left: float,
    top: float,
    right: float,
    bottom: float,
    scale: float,
    offset_x: float,
    offset_y: float,
) -> pygame.Rect:
    """Map a logical rectangle to window pixels.

    Each edge is rounded separately, so neighbouring rectangles share an edge
    with no gap or overlap.
    """
    x0 = round(offset_x + left * scale)
    y0 = round(offset_y + top * scale)
    x1 = round(offset_x + right * scale)
    y1 = round(offset_y + bottom * scale)
    return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


def draw_frame(surface: pygame.Surface, match: Match) -> None:
    """Draw one frame of ``match`` onto ``surface``.

    The whole surface is filled with black first. The playfield is scaled and
    centred with ``fit_playfield``, so the 5:3 shape is kept and the leftover
    space is black. Nothing is drawn, and ``fit_playfield`` is not called, when
    the width or height is 0. Only reads ``match``.
    """
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return

    scale, offset_x, offset_y = fit_playfield(width, height)
    surface.fill(BLACK)

    half_line = CENTRE_LINE_WIDTH / 2
    top = 0.0
    while top < PLAYFIELD_HEIGHT:
        bottom = min(top + DASH_LENGTH, PLAYFIELD_HEIGHT)
        dash = _screen_rect(
            CENTRE_LINE_X - half_line,
            top,
            CENTRE_LINE_X + half_line,
            bottom,
            scale,
            offset_x,
            offset_y,
        )
        pygame.draw.rect(surface, WHITE, dash)
        top += DASH_LENGTH + DASH_GAP

    for paddle in (match.p1, match.p2):
        rect = _screen_rect(
            paddle.x,
            paddle.y,
            paddle.x + paddle.width,
            paddle.y + paddle.height,
            scale,
            offset_x,
            offset_y,
        )
        pygame.draw.rect(surface, WHITE, rect)

    centre = (
        round(offset_x + match.ball.x * scale),
        round(offset_y + match.ball.y * scale),
    )
    pygame.draw.circle(surface, WHITE, centre, max(1, round(match.ball.radius * scale)))

    font = _digit_font(max(1, round(DIGIT_FONT_SIZE * scale)))
    for player, x in SCORE_X.items():
        digits = font.render(str(match.score.points(player)), True, WHITE)
        # Place the visible glyph, not the text box, so its centre sits on x and
        # its top sits SCORE_TOP from the top of the playfield.
        glyph = digits.get_bounding_rect()
        surface.blit(
            digits,
            (
                round(offset_x + x * scale - glyph.centerx),
                round(offset_y + SCORE_TOP * scale - glyph.y),
            ),
        )


class _PressedKeys(Protocol):
    """What ``pygame.key.get_pressed()`` returns: held state indexed by key code."""

    def __getitem__(self, key_code: int) -> bool: ...


_DEFAULT_KEYS = default_settings().bindings


def _direction(up_pressed: bool, down_pressed: bool) -> int:
    """Return -1 for up only, +1 for down only, and 0 for neither or both."""
    if up_pressed == down_pressed:
        return 0
    return -1 if up_pressed else 1


def _key_code(key_name: str, action: str) -> int:
    """Return the Pygame key code for a stored key name.

    An unknown name falls back to the action's default key, as ``load_settings``
    does for other bad values.
    """
    try:
        return pygame.key.key_code(key_name)
    except ValueError:
        return pygame.key.key_code(_DEFAULT_KEYS[action])


def _read_directions(
    pressed: _PressedKeys,
    settings: Settings,
    match: Match,
    ai: AIController,
    dt: float,
) -> tuple[int, int]:
    """Return ``(p1_direction, p2_direction)`` for this frame.

    The key names are read from ``settings.bindings`` on every call, so a rebinding
    applies on the next frame. P2 follows the keys in two-player mode and the AI in
    single-player, where the P2 keys are ignored. ``ai.update`` is called with
    ``dt`` and the ball and P2 paddle positions, and only in single-player.
    """
    codes = {
        action: _key_code(key_name, action)
        for action, key_name in settings.bindings.items()
    }
    p1_direction = _direction(pressed[codes["p1_up"]], pressed[codes["p1_down"]])
    if match.mode is Mode.SINGLE_PLAYER:
        p2_centre_y = match.p2.y + match.p2.height / 2
        p2_direction = ai.update(dt, match.ball.y, p2_centre_y)
    else:
        p2_direction = _direction(pressed[codes["p2_up"]], pressed[codes["p2_down"]])
    return p1_direction, p2_direction


def _handle_key_down(key: int, settings: Settings, match: Match) -> None:
    """Start the serve on a key press that is not a paddle key or Esc.

    ``key`` is the Pygame key code of a KEYDOWN event. The four bound paddle keys
    are read from ``settings.bindings`` on every call, so a rebinding applies at
    once. Esc is excluded because it is reserved for the pause menu. ``start_rally``
    itself does nothing unless the match is serving and not paused.
    """
    if key == pygame.K_ESCAPE:
        return
    paddle_codes = {
        _key_code(key_name, action) for action, key_name in settings.bindings.items()
    }
    if key not in paddle_codes:
        match.start_rally()


SOUNDS_DIR = Path(__file__).resolve().parent / "sounds"
"""Folder of the sound effect WAV files, made by ``scripts/make_sounds.py``."""

SOUND_FILES: dict[GameEvent, str] = {
    GameEvent.PADDLE_HIT: "paddle_hit.wav",
    GameEvent.WALL_BOUNCE: "wall_bounce.wav",
    GameEvent.SCORE: "score.wav",
    GameEvent.VICTORY: "victory.wav",
}
"""The sound that plays for each match event."""


class SoundPlayer:
    """Plays the sound for each match event, if the mixer and the files load.

    If the mixer cannot start, or a sound cannot be loaded, the player stays
    silent and the game carries on. ``play`` reads the audio settings on each
    call, so a change in the Audio screen applies at once.
    """

    def __init__(self) -> None:
        self._sounds: dict[GameEvent, pygame.mixer.Sound] = {}
        try:
            pygame.mixer.init()
            self._sounds = {
                event: pygame.mixer.Sound(str(SOUNDS_DIR / name))
                for event, name in SOUND_FILES.items()
            }
        except pygame.error:
            # No audio device, or a file failed to load: run with sound off.
            self._sounds = {}

    def play(self, events: list[GameEvent], settings: Settings) -> None:
        """Play one sound per event in ``events``, if audio is enabled.

        Each sound's volume is ``settings.volume / 100``, set just before it plays.
        Nothing plays when ``settings.audio_enabled`` is False.
        """
        if not settings.audio_enabled:
            return
        for event in events:
            sound = self._sounds.get(event)
            if sound is None:
                continue
            sound.set_volume(settings.volume / 100)
            sound.play()


# The main menu. The state and logic in this section use no pygame names: only
# draw_menu and the key mapping below touch pygame.

MENU_FONT_SIZE = 48
"""Menu text size in logical units."""
MENU_FIRST_ROW_Y = 60.0
"""Vertical centre of the first menu line, in logical units."""
MENU_ROW_SPACING = 56.0
"""Distance between the centres of neighbouring menu lines, in logical units."""
DIM_TEXT = (128, 128, 128)
"""Colour of menu lines that are not highlighted."""


class MenuItem(Enum):
    """Rows of the main menu, top to bottom."""

    START_GAME = auto()
    MODE = auto()
    DIFFICULTY = auto()
    CONTROLS = auto()
    AUDIO = auto()
    QUIT = auto()


MENU_ITEMS: tuple[MenuItem, ...] = tuple(MenuItem)


class MenuAction(Enum):
    """What a navigation key asks the menu to do."""

    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    ENTER = auto()
    BACK = auto()


class MenuOutcome(Enum):
    """What the menu asks the program to do after an action."""

    NONE = auto()
    START_GAME = auto()
    QUIT = auto()


class MenuPage(Enum):
    """Which menu screen is showing."""

    MAIN = auto()
    CONTROLS = auto()
    AUDIO = auto()


_MODE_LABELS = {Mode.SINGLE_PLAYER: "Single-player", Mode.TWO_PLAYER: "Two-player"}
_DIFFICULTY_LABELS = {
    Difficulty.EASY: "Easy",
    Difficulty.MEDIUM: "Medium",
    Difficulty.HARD: "Hard",
}


def _next_value[T](values: list[T], current: T) -> T:
    """Return the value after ``current`` in ``values``, wrapping to the first."""
    return values[(values.index(current) + 1) % len(values)]


# The Controls screen. Its state and logic use no pygame names. Key names come
# in as Pygame reports them (e.g. "w", "up") through ``ControlsScreen.capture``.

CONTROL_ACTION_LABELS: dict[str, str] = {
    "p1_up": "Player 1 up",
    "p1_down": "Player 1 down",
    "p2_up": "Player 2 up",
    "p2_down": "Player 2 down",
}
"""The rebindable actions, in the order their rows are shown, with their labels."""
_CONTROL_ACTIONS: tuple[str, ...] = tuple(CONTROL_ACTION_LABELS)
_CONTROLS_BACK_ROW = len(_CONTROL_ACTIONS)
"""Index of the Back row, which follows the four action rows."""
WAITING_TEXT = "Press a key"


class ControlsScreen:
    """The Controls screen's state: the highlighted row, the wait for a key and a message.

    Rows 0 to 3 are the paddle actions and row 4 is Back. Enter on an action row
    waits for the next key press. Esc cancels the wait. Any other key becomes the
    binding if no other action uses it, and is saved. Otherwise the binding is
    unchanged and ``message`` says which action already uses the key. A new
    binding is written to the ``settings`` object at once, so the game reads it on
    the next frame. A failed save still applies for this session.
    """

    def __init__(self, settings: Settings, path: Path) -> None:
        self.settings = settings
        self.path = path
        self.highlight = 0
        self.waiting = False
        self.message = ""

    def lines(self) -> list[str]:
        """Return the text of each row, then the message line."""
        rows = []
        for index, action in enumerate(_CONTROL_ACTIONS):
            label = CONTROL_ACTION_LABELS[action]
            if self.waiting and index == self.highlight:
                rows.append(f"{label}: {WAITING_TEXT}")
            else:
                rows.append(f"{label}: {self.settings.bindings[action].upper()}")
        rows.append("Back")
        rows.append(self.message)
        return rows

    def handle(self, action: MenuAction) -> bool:
        """Apply one navigation action. Return True when the screen should close."""
        if self.waiting:
            if action is MenuAction.BACK:
                self.waiting = False
            return False
        if action is MenuAction.BACK:
            return True
        if action is MenuAction.UP:
            self.highlight = (self.highlight - 1) % (_CONTROLS_BACK_ROW + 1)
        elif action is MenuAction.DOWN:
            self.highlight = (self.highlight + 1) % (_CONTROLS_BACK_ROW + 1)
        elif action is MenuAction.ENTER:
            if self.highlight == _CONTROLS_BACK_ROW:
                return True
            self.waiting = True
            self.message = ""
        return False

    def capture(self, key_name: str) -> None:
        """Handle the key press that ends the wait, given its Pygame key name.

        Does nothing unless the screen is waiting. Esc cancels the wait. A key
        Pygame has no name for is ignored, and the wait goes on.
        """
        if not self.waiting:
            return
        if key_name.lower() == RESERVED_KEY:
            self.waiting = False
            return
        if not key_name:
            return

        action = _CONTROL_ACTIONS[self.highlight]
        self.waiting = False
        candidate = dict(self.settings.bindings)
        candidate[action] = key_name
        if find_binding_conflicts(candidate):
            holder = next(
                (
                    other
                    for other in _CONTROL_ACTIONS
                    if other != action and candidate[other].lower() == key_name.lower()
                ),
                None,
            )
            key_text = key_name.upper()
            if holder is None:
                self.message = f"{key_text} cannot be used"
            else:
                self.message = (
                    f"{key_text} is already used by {CONTROL_ACTION_LABELS[holder]}"
                )
            return

        self.settings.bindings = candidate
        self.message = ""
        # save_settings returns False when the file cannot be written. The new
        # binding is already in self.settings, so it still applies for this session.
        save_settings(self.path, self.settings)


class AudioItem(Enum):
    """Rows of the Audio screen, top to bottom."""

    SOUND = auto()
    VOLUME = auto()
    BACK = auto()


AUDIO_ITEMS: tuple[AudioItem, ...] = tuple(AudioItem)
VOLUME_STEP = 10
"""How much one Left or Right press changes the volume, in percentage points."""


class AudioScreen:
    """The Audio screen's state: the highlighted row and the audio settings.

    Enter on Sound toggles it between On and Off. Left and Right on Volume change
    the volume by ``VOLUME_STEP`` and stop at 0 and 100. Volume can change while
    sound is off. Each change is written to ``path`` at once, and a failed write
    still applies for this session. Back, Enter on Back and Esc close the screen,
    which ``handle`` reports by returning True.
    """

    def __init__(self, settings: Settings, path: Path) -> None:
        self.settings = settings
        self.path = path
        self.highlight = 0

    @property
    def selected(self) -> AudioItem:
        """Return the highlighted row."""
        return AUDIO_ITEMS[self.highlight]

    def lines(self) -> list[str]:
        """Return the text of each row, top to bottom."""
        sound = "On" if self.settings.audio_enabled else "Off"
        return [f"Sound: {sound}", f"Volume: {self.settings.volume}", "Back"]

    def handle(self, action: MenuAction) -> bool:
        """Apply one navigation action. Return True when the screen should close."""
        if action is MenuAction.BACK:
            return True
        if action is MenuAction.UP:
            self.highlight = (self.highlight - 1) % len(AUDIO_ITEMS)
        elif action is MenuAction.DOWN:
            self.highlight = (self.highlight + 1) % len(AUDIO_ITEMS)
        elif action is MenuAction.ENTER:
            if self.selected is AudioItem.BACK:
                return True
            if self.selected is AudioItem.SOUND:
                self.settings.audio_enabled = not self.settings.audio_enabled
                self._save()
        elif action in (MenuAction.LEFT, MenuAction.RIGHT) and (
            self.selected is AudioItem.VOLUME
        ):
            step = -VOLUME_STEP if action is MenuAction.LEFT else VOLUME_STEP
            volume = min(100, max(0, self.settings.volume + step))
            if volume != self.settings.volume:
                self.settings.volume = volume
                self._save()
        return False

    def _save(self) -> None:
        # save_settings returns False when the file cannot be written. The value
        # is already in self.settings, so it still applies for this session.
        save_settings(self.path, self.settings)


class MainMenu:
    """The main menu's state: the screen, the highlighted row and the settings.

    ``settings`` is the object the rest of the program reads, so a change made
    here applies at once. A mode or difficulty change is written to ``path``
    straight away. If the write fails the value still applies for this session.
    The Controls and Audio screens are opened from here and handle their own keys.
    """

    def __init__(self, settings: Settings, path: Path) -> None:
        self.settings = settings
        self.path = path
        self.page = MenuPage.MAIN
        self.highlight = 0
        self.controls = ControlsScreen(settings, path)
        self.audio = AudioScreen(settings, path)

    @property
    def selected(self) -> MenuItem:
        """Return the highlighted row of the main menu."""
        return MENU_ITEMS[self.highlight]

    @property
    def highlighted_line(self) -> int:
        """Return the index in ``lines`` of the highlighted line."""
        if self.page is MenuPage.MAIN:
            return self.highlight
        if self.page is MenuPage.CONTROLS:
            return self.controls.highlight
        if self.page is MenuPage.AUDIO:
            return self.audio.highlight
        return self.highlight

    @property
    def capturing(self) -> bool:
        """Return True while the Controls screen waits for a key to bind."""
        return self.page is MenuPage.CONTROLS and self.controls.waiting

    def capture(self, key_name: str) -> None:
        """Pass the Pygame name of the key that ends a binding wait to the Controls screen."""
        self.controls.capture(key_name)

    def lines(self) -> list[str]:
        """Return the text of each line of the current screen, top to bottom."""
        if self.page is MenuPage.CONTROLS:
            return self.controls.lines()
        if self.page is MenuPage.AUDIO:
            return self.audio.lines()
        labels = {
            MenuItem.START_GAME: "Start Game",
            MenuItem.MODE: f"Mode: {_MODE_LABELS[self.settings.mode]}",
            MenuItem.DIFFICULTY: (
                f"Difficulty: {_DIFFICULTY_LABELS[self.settings.difficulty]}"
            ),
            MenuItem.CONTROLS: "Controls",
            MenuItem.AUDIO: "Audio",
            MenuItem.QUIT: "Quit",
        }
        return [labels[item] for item in MENU_ITEMS]

    def handle(self, action: MenuAction) -> MenuOutcome:
        """Apply one navigation action and return what the program should do next."""
        if self.page is MenuPage.CONTROLS:
            if self.controls.handle(action):
                self.page = MenuPage.MAIN
            return MenuOutcome.NONE
        if self.page is MenuPage.AUDIO:
            if self.audio.handle(action):
                self.page = MenuPage.MAIN
            return MenuOutcome.NONE
        if action is MenuAction.UP:
            self.highlight = (self.highlight - 1) % len(MENU_ITEMS)
            return MenuOutcome.NONE
        if action is MenuAction.DOWN:
            self.highlight = (self.highlight + 1) % len(MENU_ITEMS)
            return MenuOutcome.NONE
        if action is not MenuAction.ENTER:
            # Esc, Left and Right do nothing on the main menu.
            return MenuOutcome.NONE

        item = self.selected
        if item is MenuItem.START_GAME:
            return MenuOutcome.START_GAME
        if item is MenuItem.QUIT:
            return MenuOutcome.QUIT
        if item is MenuItem.MODE:
            self.settings.mode = _next_value(list(Mode), self.settings.mode)
            self._save()
        elif item is MenuItem.DIFFICULTY:
            self.settings.difficulty = _next_value(
                list(Difficulty), self.settings.difficulty
            )
            self._save()
        elif item is MenuItem.CONTROLS:
            # A fresh screen each time, so it opens with no wait and no message.
            self.controls = ControlsScreen(self.settings, self.path)
            self.page = MenuPage.CONTROLS
        elif item is MenuItem.AUDIO:
            # A fresh screen each time, so it opens on the Sound row.
            self.audio = AudioScreen(self.settings, self.path)
            self.page = MenuPage.AUDIO
        return MenuOutcome.NONE

    def _save(self) -> None:
        # save_settings returns False when the file cannot be written. The value
        # is already in self.settings, so it still applies for this session.
        save_settings(self.path, self.settings)


_MENU_KEYS: dict[int, MenuAction] = {
    pygame.K_UP: MenuAction.UP,
    pygame.K_DOWN: MenuAction.DOWN,
    pygame.K_LEFT: MenuAction.LEFT,
    pygame.K_RIGHT: MenuAction.RIGHT,
    pygame.K_RETURN: MenuAction.ENTER,
    pygame.K_ESCAPE: MenuAction.BACK,
}


def _handle_menu_key(key: int, menu: MainMenu) -> MenuOutcome:
    """Pass a KEYDOWN key code to the menu. Keys that are not menu keys do nothing.

    While the Controls screen waits for a key, every key press is the new binding
    (or Esc to cancel), so the key's Pygame name goes to the menu instead.
    """
    if menu.capturing:
        menu.capture(pygame.key.name(key))
        return MenuOutcome.NONE
    action = _MENU_KEYS.get(key)
    if action is None:
        return MenuOutcome.NONE
    return menu.handle(action)


# The pause menu, opened with Esc during a match. Like the main menu, its state
# and logic use no pygame names. It uses the same fixed navigation keys.

PAUSE_FIRST_ROW_Y = 244.0
"""Vertical centre of the first pause line, in logical units. Centres the three lines."""
PAUSE_ROW_SPACING = 56.0
"""Distance between the centres of neighbouring pause lines, in logical units."""
PAUSE_SHADE_ALPHA = 160
"""Opacity of the black shade drawn over the frozen playfield, from 0 to 255."""


class PauseItem(Enum):
    """Rows of the pause menu, top to bottom."""

    RESUME = auto()
    RESTART = auto()
    MAIN_MENU = auto()


PAUSE_ITEMS: tuple[PauseItem, ...] = tuple(PauseItem)

_PAUSE_LABELS = {
    PauseItem.RESUME: "Resume",
    PauseItem.RESTART: "Restart Match",
    PauseItem.MAIN_MENU: "Main Menu",
}


class PauseOutcome(Enum):
    """What the pause menu asks the program to do after an action."""

    NONE = auto()
    RESUME = auto()
    RESTART = auto()
    MAIN_MENU = auto()


_PAUSE_OUTCOMES = {
    PauseItem.RESUME: PauseOutcome.RESUME,
    PauseItem.RESTART: PauseOutcome.RESTART,
    PauseItem.MAIN_MENU: PauseOutcome.MAIN_MENU,
}


class PauseMenu:
    """The pause menu's state: which row is highlighted.

    The highlight starts on Resume. Up and Down wrap around. Enter activates the
    highlighted row, and Esc resumes, as Resume does.
    """

    def __init__(self) -> None:
        self.highlight = 0

    @property
    def selected(self) -> PauseItem:
        """Return the highlighted row."""
        return PAUSE_ITEMS[self.highlight]

    def lines(self) -> list[str]:
        """Return the text of each row, top to bottom."""
        return [_PAUSE_LABELS[item] for item in PAUSE_ITEMS]

    def handle(self, action: MenuAction) -> PauseOutcome:
        """Apply one navigation action and return what the program should do next."""
        if action is MenuAction.UP:
            self.highlight = (self.highlight - 1) % len(PAUSE_ITEMS)
            return PauseOutcome.NONE
        if action is MenuAction.DOWN:
            self.highlight = (self.highlight + 1) % len(PAUSE_ITEMS)
            return PauseOutcome.NONE
        if action is MenuAction.BACK:
            return PauseOutcome.RESUME
        if action is not MenuAction.ENTER:
            # Left and Right do nothing in the pause menu.
            return PauseOutcome.NONE
        return _PAUSE_OUTCOMES[self.selected]


def _handle_pause_key(key: int, pause: PauseMenu) -> PauseOutcome:
    """Pass a KEYDOWN key code to the pause menu. Keys that are not menu keys do nothing."""
    action = _MENU_KEYS.get(key)
    if action is None:
        return PauseOutcome.NONE
    return pause.handle(action)


# The game-over screen, shown when a match is won. Its state and logic use no
# pygame names. It uses the same fixed navigation keys as the other menus.

GAME_OVER_TITLE_Y = 120.0
"""Vertical centre of the winner line, in logical units."""
GAME_OVER_LABEL_Y = 200.0
"""Vertical centre of the side labels above the final score, in logical units."""
GAME_OVER_SCORE_Y = 260.0
"""Vertical centre of the final score, in logical units."""
GAME_OVER_FIRST_ROW_Y = 400.0
"""Vertical centre of the first option, in logical units."""
SCORE_SEPARATOR = "–"
"""The en dash between the two scores, as in "11 – 7"."""


class GameOverItem(Enum):
    """Rows of the game-over screen, top to bottom."""

    REMATCH = auto()
    MAIN_MENU = auto()
    QUIT = auto()


GAME_OVER_ITEMS: tuple[GameOverItem, ...] = tuple(GameOverItem)

_GAME_OVER_LABELS = {
    GameOverItem.REMATCH: "Rematch",
    GameOverItem.MAIN_MENU: "Main Menu",
    GameOverItem.QUIT: "Quit",
}


class GameOverOutcome(Enum):
    """What the game-over screen asks the program to do after an action."""

    NONE = auto()
    REMATCH = auto()
    MAIN_MENU = auto()
    QUIT = auto()


_GAME_OVER_OUTCOMES = {
    GameOverItem.REMATCH: GameOverOutcome.REMATCH,
    GameOverItem.MAIN_MENU: GameOverOutcome.MAIN_MENU,
    GameOverItem.QUIT: GameOverOutcome.QUIT,
}


def side_label(player: Player, mode: Mode) -> str:
    """Return the name shown for ``player``: the right side is "Computer" in single-player."""
    if player is Player.P1:
        return "Player 1"
    if mode is Mode.SINGLE_PLAYER:
        return "Computer"
    return "Player 2"


class GameOverScreen:
    """The game-over screen's state: the winner, the final score and the highlighted option.

    Built from a match that has a winner. The scores are copied when the screen is
    built. The highlight starts on Rematch. Up and Down wrap around. Enter activates
    the highlighted option. Esc, Left and Right do nothing here, so Esc does not open
    the pause menu.
    """

    def __init__(self, match: Match) -> None:
        winner = match.score.winner()
        if winner is None:
            raise ValueError("the game-over screen needs a match with a winner")
        self.winner = winner
        self.mode = match.mode
        self.points = {player: match.score.points(player) for player in Player}
        self.highlight = 0

    @property
    def selected(self) -> GameOverItem:
        """Return the highlighted option."""
        return GAME_OVER_ITEMS[self.highlight]

    def label(self, player: Player) -> str:
        """Return the name shown for ``player`` on this screen."""
        return side_label(player, self.mode)

    def winner_text(self) -> str:
        """Return the winner line, for example "Player 1 wins"."""
        return f"{self.label(self.winner)} wins"

    def score_text(self) -> str:
        """Return the final score, for example "11 – 7", in Player 1 then Player 2 order."""
        return f"{self.points[Player.P1]} {SCORE_SEPARATOR} {self.points[Player.P2]}"

    def lines(self) -> list[str]:
        """Return the text of each option, top to bottom."""
        return [_GAME_OVER_LABELS[item] for item in GAME_OVER_ITEMS]

    def handle(self, action: MenuAction) -> GameOverOutcome:
        """Apply one navigation action and return what the program should do next."""
        if action is MenuAction.UP:
            self.highlight = (self.highlight - 1) % len(GAME_OVER_ITEMS)
            return GameOverOutcome.NONE
        if action is MenuAction.DOWN:
            self.highlight = (self.highlight + 1) % len(GAME_OVER_ITEMS)
            return GameOverOutcome.NONE
        if action is not MenuAction.ENTER:
            # Esc, Left and Right do nothing on the game-over screen.
            return GameOverOutcome.NONE
        return _GAME_OVER_OUTCOMES[self.selected]


def _handle_game_over_key(key: int, screen: GameOverScreen) -> GameOverOutcome:
    """Pass a KEYDOWN key code to the game-over screen. Keys that are not menu keys do nothing.

    Paddle and rally keys are not menu keys, so they do nothing here.
    """
    action = _MENU_KEYS.get(key)
    if action is None:
        return GameOverOutcome.NONE
    return screen.handle(action)


def _start_match(settings: Settings) -> tuple[Match, AIController]:
    """Return a new match in the serving state, with the AI for its difficulty."""
    match = Match(settings.mode, settings.difficulty)
    return match, AIController(settings.difficulty, random.Random())


def _restart_match(match: Match, settings: Settings) -> AIController:
    """Reset ``match`` to a fresh serving match and return a new AI controller.

    The controller is new so its reaction timers start over, as they do at the
    start of a match.
    """
    match.restart()
    return AIController(settings.difficulty, random.Random())


@functools.lru_cache(maxsize=4)
def _menu_font(size: int) -> pygame.font.Font:
    """Return the default font at ``size`` pixels, cached by size."""
    return pygame.font.Font(None, size)


def _draw_lines(
    surface: pygame.Surface,
    lines: list[str],
    highlighted: int,
    first_row_y: float,
    row_spacing: float,
) -> None:
    """Draw ``lines`` centred across the playfield, one per row, without filling.

    Rows are placed in logical units, starting with the centre of the first row
    at ``first_row_y``. The line at index ``highlighted`` is white, the others dim.
    """
    scale, offset_x, offset_y = fit_playfield(*surface.get_size())
    font = _menu_font(max(1, round(MENU_FONT_SIZE * scale)))
    centre_x = round(offset_x + PLAYFIELD_WIDTH / 2 * scale)
    for index, text in enumerate(lines):
        colour = WHITE if index == highlighted else DIM_TEXT
        rendered = font.render(text, True, colour)
        centre_y = round(offset_y + (first_row_y + index * row_spacing) * scale)
        surface.blit(rendered, rendered.get_rect(center=(centre_x, centre_y)))


def draw_menu(surface: pygame.Surface, menu: MainMenu) -> None:
    """Draw the current menu screen onto ``surface``.

    The surface is filled with black, and the lines are centred in the 5:3
    playfield area as ``draw_frame`` maps it. The highlighted line is white and
    the others are dim. Nothing is drawn when the width or height is 0. Only
    reads ``menu``.
    """
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return

    surface.fill(BLACK)
    _draw_lines(
        surface,
        menu.lines(),
        menu.highlighted_line,
        MENU_FIRST_ROW_Y,
        MENU_ROW_SPACING,
    )


def draw_pause_menu(surface: pygame.Surface, pause: PauseMenu) -> None:
    """Draw the pause menu over the playfield already drawn on ``surface``.

    The whole surface is shaded with black at ``PAUSE_SHADE_ALPHA``, so the frozen
    playfield stays visible underneath. The rows are drawn over the shade, with the
    highlighted row white and the others dim. Nothing is drawn when the width or
    height is 0. Only reads ``pause``.
    """
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return

    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    shade.fill((*BLACK, PAUSE_SHADE_ALPHA))
    surface.blit(shade, (0, 0))
    _draw_lines(
        surface,
        pause.lines(),
        pause.highlight,
        PAUSE_FIRST_ROW_Y,
        PAUSE_ROW_SPACING,
    )


def draw_game_over(surface: pygame.Surface, screen: GameOverScreen) -> None:
    """Draw the game-over screen onto ``surface``, replacing the match view.

    The surface is filled with black. The winner line, the side labels and the final
    score are centred in the 5:3 playfield area as ``draw_frame`` maps it, then the
    options. The highlighted option is white and the others are dim. Nothing is drawn
    when the width or height is 0. Only reads ``screen``.
    """
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return

    surface.fill(BLACK)
    scale, offset_x, offset_y = fit_playfield(width, height)
    menu_font = _menu_font(max(1, round(MENU_FONT_SIZE * scale)))
    score_font = _digit_font(max(1, round(DIGIT_FONT_SIZE * scale)))
    centre_x = PLAYFIELD_WIDTH / 2

    def put(text: str, font: pygame.font.Font, colour: tuple[int, int, int], x, y):
        rendered = font.render(text, True, colour)
        centre = (round(offset_x + x * scale), round(offset_y + y * scale))
        surface.blit(rendered, rendered.get_rect(center=centre))

    put(screen.winner_text(), menu_font, WHITE, centre_x, GAME_OVER_TITLE_Y)
    for player, x in SCORE_X.items():
        put(screen.label(player), menu_font, DIM_TEXT, x, GAME_OVER_LABEL_Y)
    put(screen.score_text(), score_font, WHITE, centre_x, GAME_OVER_SCORE_Y)
    for index, text in enumerate(screen.lines()):
        colour = WHITE if index == screen.highlight else DIM_TEXT
        y = GAME_OVER_FIRST_ROW_Y + index * MENU_ROW_SPACING
        put(text, menu_font, colour, centre_x, y)


def main() -> int:
    pygame.init()
    # Loaded once. Bindings are read from this object each frame, not the file.
    path = config_path(os.environ, Path.home())
    settings = load_settings(path)
    menu = MainMenu(settings, path)
    sounds = SoundPlayer()
    screen = pygame.display.set_mode(
        (PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT), pygame.RESIZABLE
    )
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()
    # Both are None while the menu is showing. Start Game sets them.
    match: Match | None = None
    ai: AIController | None = None
    # Set while the pause menu is open during a match. Its match is paused.
    pause: PauseMenu | None = None
    # Set from the frame a match is won until Rematch or Main Menu. Its match is over.
    game_over: GameOverScreen | None = None

    running = True
    while running:
        # Seconds since the previous frame, capped at MAX_DT, so a paddle or the
        # ball moves the same distance per second whatever the frame rate.
        dt = min(clock.tick(FPS) / 1000.0, MAX_DT)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if match is None or ai is None:
                    outcome = _handle_menu_key(event.key, menu)
                    if outcome is MenuOutcome.START_GAME:
                        match, ai = _start_match(menu.settings)
                    elif outcome is MenuOutcome.QUIT:
                        running = False
                elif game_over is not None:
                    # Paddle and rally keys do nothing here, and Esc does not pause.
                    over_outcome = _handle_game_over_key(event.key, game_over)
                    if over_outcome is GameOverOutcome.REMATCH:
                        ai = _restart_match(match, settings)
                        game_over = None
                    elif over_outcome is GameOverOutcome.MAIN_MENU:
                        match = None
                        ai = None
                        game_over = None
                    elif over_outcome is GameOverOutcome.QUIT:
                        running = False
                elif pause is not None:
                    pause_outcome = _handle_pause_key(event.key, pause)
                    if pause_outcome is PauseOutcome.RESUME:
                        match.toggle_pause()
                        pause = None
                    elif pause_outcome is PauseOutcome.RESTART:
                        ai = _restart_match(match, settings)
                        pause = None
                    elif pause_outcome is PauseOutcome.MAIN_MENU:
                        match = None
                        ai = None
                        pause = None
                elif event.key == pygame.K_ESCAPE:
                    # toggle_pause does nothing once someone has won, so the menu
                    # opens only if the match really paused.
                    match.toggle_pause()
                    if match.paused:
                        pause = PauseMenu()
                else:
                    _handle_key_down(event.key, settings, match)
            # VIDEORESIZE is not handled. Calling set_mode on each resize event
            # re-set the window size while the user was still dragging it, which
            # is the likely cause of the window shifting. pygame keeps the display
            # surface at the window's size, and every draw call reads that size, so
            # the playfield rescales without set_mode.

        if match is not None and ai is not None:
            # While paused, or once the match is won, the simulation and the AI are
            # not advanced, so the playfield stays frozen and the AI's timers stop.
            if pause is None and game_over is None:
                p1_direction, p2_direction = _read_directions(
                    pygame.key.get_pressed(), settings, match, ai, dt
                )
                events = match.update(dt, p1_direction, p2_direction)
                sounds.play(events, settings)
                if GameEvent.VICTORY in events:
                    game_over = GameOverScreen(match)
            if game_over is not None:
                draw_game_over(screen, game_over)
            else:
                draw_frame(screen, match)
                if pause is not None:
                    draw_pause_menu(screen, pause)
        else:
            draw_menu(screen, menu)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
