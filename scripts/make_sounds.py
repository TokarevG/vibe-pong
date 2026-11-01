"""Generate the sound effects in ``pong/sounds/`` using only the standard library.

Run with ``python scripts/make_sounds.py``. The output is deterministic, so
running it again rewrites the same bytes. The generated WAV files are committed,
so the game does not need this script to run.
"""

import math
import struct
import wave
from collections.abc import Sequence
from pathlib import Path

SAMPLE_RATE = 22050
"""Samples per second. Mono, 16-bit."""
PEAK = 0.6
"""Largest sample value as a fraction of full scale, so the sounds are not harsh."""

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "pong" / "sounds"


def _tone(frequency: float, duration: float, decay: float) -> list[float]:
    """Return a sine tone with an exponential fade-out, samples in -1.0 to 1.0.

    ``decay`` is the time constant of the fade in seconds. A short ``decay``
    gives a click-like sound, a long one a ring.
    """
    count = round(duration * SAMPLE_RATE)
    samples = []
    for index in range(count):
        t = index / SAMPLE_RATE
        envelope = math.exp(-t / decay)
        samples.append(math.sin(2 * math.pi * frequency * t) * envelope)
    return samples


def _sweep(start: float, end: float, duration: float, decay: float) -> list[float]:
    """Return a tone whose pitch glides linearly from ``start`` to ``end`` Hz."""
    count = round(duration * SAMPLE_RATE)
    samples = []
    phase = 0.0
    for index in range(count):
        t = index / SAMPLE_RATE
        frequency = start + (end - start) * (index / count)
        phase += 2 * math.pi * frequency / SAMPLE_RATE
        samples.append(math.sin(phase) * math.exp(-t / decay))
    return samples


def _notes(
    frequencies: Sequence[float], note_duration: float, decay: float
) -> list[float]:
    """Return the notes played one after another, each with its own fade."""
    samples: list[float] = []
    for frequency in frequencies:
        samples.extend(_tone(frequency, note_duration, decay))
    return samples


def _paddle_hit() -> list[float]:
    """A short, bright blip for the ball meeting a paddle."""
    return _tone(880.0, 0.08, decay=0.03)


def _wall_bounce() -> list[float]:
    """A lower, softer tick for the ball touching the top or bottom wall."""
    return _tone(220.0, 0.06, decay=0.02)


def _score() -> list[float]:
    """A falling tone for a point being lost."""
    return _sweep(660.0, 220.0, 0.35, decay=0.2)


def _victory() -> list[float]:
    """A rising three-note arpeggio for winning the match."""
    return _notes([523.25, 659.25, 783.99], note_duration=0.2, decay=0.25)


SOUNDS = {
    "paddle_hit.wav": _paddle_hit,
    "wall_bounce.wav": _wall_bounce,
    "score.wav": _score,
    "victory.wav": _victory,
}


def write_wav(path: Path, samples: Sequence[float]) -> None:
    """Write ``samples`` (from -1.0 to 1.0) to ``path`` as 16-bit mono WAV."""
    frames = b"".join(
        struct.pack("<h", round(max(-1.0, min(1.0, s)) * PEAK * 32767)) for s in samples
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)


def generate(directory: Path) -> None:
    """Write all four sound effects into ``directory``, creating it if needed."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        write_wav(directory / name, make())


if __name__ == "__main__":
    generate(SOUNDS_DIR)
    for name in SOUNDS:
        print(f"wrote {SOUNDS_DIR / name}")
