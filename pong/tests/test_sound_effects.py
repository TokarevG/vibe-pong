import ast
import importlib.util
import os
import tomllib
import wave
from pathlib import Path
from typing import cast

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.__main__ import SOUND_FILES, SOUNDS_DIR, SoundPlayer
from pong.game import GameEvent
from pong.settings import Settings

pygame = main_module.pygame

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "make_sounds.py"
EXPECTED_FILES = {
    "paddle_hit.wav",
    "wall_bounce.wav",
    "score.wav",
    "victory.wav",
}


def _load_script():
    spec = importlib.util.spec_from_file_location("make_sounds", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSound:
    """Stands in for pygame.mixer.Sound and records calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.plays = 0
        self.volumes: list[float] = []

    def set_volume(self, volume: float) -> None:
        self.volumes.append(volume)

    def play(self) -> None:
        self.plays += 1


def _fake_sounds(player: SoundPlayer) -> dict[GameEvent, FakeSound]:
    """Return the player's sounds, typed as the fakes this module installs."""
    return cast(dict[GameEvent, FakeSound], player._sounds)


def _fake_player(monkeypatch: pytest.MonkeyPatch) -> SoundPlayer:
    """Build a SoundPlayer whose sounds are FakeSound objects."""
    monkeypatch.setattr(pygame.mixer, "init", lambda *a, **k: None)
    monkeypatch.setattr(pygame.mixer, "Sound", FakeSound)
    return SoundPlayer()


def test_four_wav_files_are_present_and_under_one_second() -> None:
    assert {p.name for p in SOUNDS_DIR.glob("*.wav")} == EXPECTED_FILES
    for name in EXPECTED_FILES:
        with wave.open(str(SOUNDS_DIR / name), "rb") as handle:
            duration = handle.getnframes() / handle.getframerate()
        assert 0 < duration < 1.0, name


def test_each_sound_file_is_mapped_to_one_event() -> None:
    assert set(SOUND_FILES) == set(GameEvent)
    assert set(SOUND_FILES.values()) == EXPECTED_FILES


def test_script_generates_the_committed_files_byte_for_byte(tmp_path: Path) -> None:
    module = _load_script()
    module.generate(tmp_path)
    for name in EXPECTED_FILES:
        assert (tmp_path / name).read_bytes() == (SOUNDS_DIR / name).read_bytes(), name


def test_script_uses_only_the_standard_library() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    stdlib = {"math", "struct", "wave", "collections", "pathlib"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= stdlib


def test_pyproject_includes_sound_files_as_package_data() -> None:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "sounds/*.wav" in package_data["pong"]
    # No new runtime dependency.
    assert data["project"]["dependencies"] == ["pygame-ce>=2.5.8"]


def test_each_event_plays_its_own_sound_once_per_occurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player = _fake_player(monkeypatch)
    settings = Settings()
    for event in GameEvent:
        player.play([event], settings)
    for event in GameEvent:
        assert _fake_sounds(player)[event].plays == 1, event

    player.play([GameEvent.PADDLE_HIT, GameEvent.PADDLE_HIT], settings)
    assert _fake_sounds(player)[GameEvent.PADDLE_HIT].plays == 3


def test_no_events_plays_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    player = _fake_player(monkeypatch)
    player.play([], Settings())
    assert all(sound.plays == 0 for sound in _fake_sounds(player).values())


def test_volume_is_saved_volume_divided_by_100(monkeypatch: pytest.MonkeyPatch) -> None:
    player = _fake_player(monkeypatch)
    settings = Settings(volume=80)
    player.play([GameEvent.SCORE], settings)
    settings.volume = 25
    player.play([GameEvent.SCORE], settings)
    assert _fake_sounds(player)[GameEvent.SCORE].volumes == [0.8, 0.25]


def test_nothing_plays_when_audio_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    player = _fake_player(monkeypatch)
    settings = Settings(audio_enabled=False)
    for event in GameEvent:
        player.play([event], settings)
    assert all(sound.plays == 0 for sound in _fake_sounds(player).values())
    assert all(sound.volumes == [] for sound in _fake_sounds(player).values())


def test_turning_sound_off_then_on_applies_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player = _fake_player(monkeypatch)
    settings = Settings(audio_enabled=True)
    player.play([GameEvent.WALL_BOUNCE], settings)
    settings.audio_enabled = False
    player.play([GameEvent.WALL_BOUNCE], settings)
    settings.audio_enabled = True
    player.play([GameEvent.WALL_BOUNCE], settings)
    assert _fake_sounds(player)[GameEvent.WALL_BOUNCE].plays == 2


def test_mixer_init_failure_leaves_sound_off_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "init", fail)
    player = SoundPlayer()
    player.play([GameEvent.PADDLE_HIT, GameEvent.VICTORY], Settings())


def test_sound_load_failure_leaves_sound_off_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise pygame.error("cannot load")

    monkeypatch.setattr(pygame.mixer, "init", lambda *a, **k: None)
    monkeypatch.setattr(pygame.mixer, "Sound", fail)
    player = SoundPlayer()
    player.play([GameEvent.SCORE], Settings())


def test_real_mixer_loads_sounds_headless() -> None:
    # SDL_AUDIODRIVER is set to dummy above, so this runs without a device.
    player = SoundPlayer()
    assert set(_fake_sounds(player)) == set(GameEvent)
    player.play(list(GameEvent), Settings())
