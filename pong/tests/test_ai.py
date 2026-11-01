import ast
import dataclasses
from pathlib import Path

import pytest

from pong.ai import AI_SETTINGS, AISettings, Difficulty

AI_SOURCE = Path(__file__).parent.parent / "ai.py"


def test_module_does_not_import_pygame():
    tree = ast.parse(AI_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "pygame" for name in imported)


def test_difficulty_has_easy_medium_hard():
    assert {d.name for d in Difficulty} == {"EASY", "MEDIUM", "HARD"}


def test_ai_settings_is_frozen():
    settings = AI_SETTINGS[Difficulty.EASY]
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.max_speed = 1.0  # type: ignore[misc]


def test_ai_settings_has_the_three_fields():
    names = {f.name for f in dataclasses.fields(AISettings)}
    assert names == {"reaction_delay", "max_speed", "aim_error"}


def test_table_has_an_entry_for_every_difficulty():
    assert set(AI_SETTINGS) == set(Difficulty)


@pytest.mark.parametrize(
    ("difficulty", "reaction_delay", "max_speed", "aim_error"),
    [
        (Difficulty.EASY, 0.40, 240, 60),
        (Difficulty.MEDIUM, 0.25, 330, 30),
        (Difficulty.HARD, 0.10, 420, 10),
    ],
)
def test_table_values(difficulty, reaction_delay, max_speed, aim_error):
    assert AI_SETTINGS[difficulty] == AISettings(
        reaction_delay=reaction_delay,
        max_speed=max_speed,
        aim_error=aim_error,
    )


def test_reaction_delay_is_easy_then_medium_then_hard():
    s = AI_SETTINGS
    assert (
        s[Difficulty.EASY].reaction_delay
        > s[Difficulty.MEDIUM].reaction_delay
        > s[Difficulty.HARD].reaction_delay
    )


def test_max_speed_is_easy_then_medium_then_hard():
    s = AI_SETTINGS
    assert (
        s[Difficulty.EASY].max_speed
        < s[Difficulty.MEDIUM].max_speed
        < s[Difficulty.HARD].max_speed
    )


def test_aim_error_is_easy_then_medium_then_hard():
    s = AI_SETTINGS
    assert (
        s[Difficulty.EASY].aim_error
        > s[Difficulty.MEDIUM].aim_error
        > s[Difficulty.HARD].aim_error
    )
