import ast
import dataclasses
from pathlib import Path

import pytest

from pong.ai import Difficulty
from pong.game import Mode
from pong.settings import (
    Settings,
    config_path,
    default_settings,
    find_binding_conflicts,
)

SETTINGS_SOURCE = Path(__file__).parent.parent / "settings.py"
HOME = Path("/home/tester")


def test_module_does_not_import_pygame():
    tree = ast.parse(SETTINGS_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "pygame" for name in imported)


def test_module_does_not_read_environment_or_home():
    tree = ast.parse(SETTINGS_SOURCE.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "os" not in imported
    source = SETTINGS_SOURCE.read_text()
    assert "expanduser" not in source
    assert "Path.home" not in source


def test_settings_has_the_five_fields():
    names = {f.name for f in dataclasses.fields(Settings)}
    assert names == {"mode", "difficulty", "audio_enabled", "volume", "bindings"}


def test_default_values():
    settings = default_settings()
    assert settings.mode is Mode.SINGLE_PLAYER
    assert settings.difficulty is Difficulty.MEDIUM
    assert settings.audio_enabled is True
    assert settings.volume == 80
    assert settings.bindings == {
        "p1_up": "w",
        "p1_down": "s",
        "p2_up": "up",
        "p2_down": "down",
    }


def test_volume_is_an_integer_in_range():
    volume = default_settings().volume
    assert isinstance(volume, int)
    assert 0 <= volume <= 100


def test_key_names_are_lowercase_pygame_names():
    for key in default_settings().bindings.values():
        assert key
        assert key == key.lower()
        assert " " not in key


def test_default_settings_returns_a_new_object_each_call():
    first = default_settings()
    second = default_settings()
    assert first is not second


def test_changing_one_result_does_not_change_later_results():
    first = default_settings()
    first.bindings["p1_up"] = "i"
    first.volume = 0
    first.mode = Mode.TWO_PLAYER
    second = default_settings()
    assert second.bindings["p1_up"] == "w"
    assert second.volume == 80
    assert second.mode is Mode.SINGLE_PLAYER


def test_config_path_uses_xdg_config_home_when_set():
    env = {"XDG_CONFIG_HOME": "/custom/config"}
    assert config_path(env, HOME) == Path("/custom/config/pong/config.json")


def test_config_path_falls_back_to_home_when_xdg_unset():
    assert config_path({}, HOME) == Path("/home/tester/.config/pong/config.json")


def test_config_path_falls_back_to_home_when_xdg_empty():
    env = {"XDG_CONFIG_HOME": ""}
    assert config_path(env, HOME) == Path("/home/tester/.config/pong/config.json")


def test_config_path_falls_back_to_home_when_xdg_relative():
    env = {"XDG_CONFIG_HOME": "relative/config"}
    assert config_path(env, HOME) == Path("/home/tester/.config/pong/config.json")


def test_config_path_uses_the_given_home_not_the_real_one():
    other_home = Path("/elsewhere/user")
    assert config_path({}, other_home) == Path(
        "/elsewhere/user/.config/pong/config.json"
    )


def test_default_bindings_have_no_conflicts():
    assert find_binding_conflicts(default_settings().bindings) == []


def test_valid_custom_set_has_no_conflicts():
    bindings = {"p1_up": "i", "p1_down": "k", "p2_up": "o", "p2_down": "l"}
    assert find_binding_conflicts(bindings) == []


def test_duplicate_key_lists_both_actions():
    bindings = {"p1_up": "w", "p1_down": "s", "p2_up": "w", "p2_down": "down"}
    assert find_binding_conflicts(bindings) == ["p1_up", "p2_up"]


def test_duplicate_key_lists_all_actions_sharing_it():
    bindings = {"p1_up": "a", "p1_down": "a", "p2_up": "a", "p2_down": "down"}
    assert find_binding_conflicts(bindings) == ["p1_down", "p1_up", "p2_up"]


def test_key_comparison_ignores_case():
    bindings = {"p1_up": "W", "p1_down": "s", "p2_up": "w", "p2_down": "down"}
    assert find_binding_conflicts(bindings) == ["p1_up", "p2_up"]


def test_esc_as_paddle_key_is_a_conflict():
    bindings = {"p1_up": "escape", "p1_down": "s", "p2_up": "up", "p2_down": "down"}
    assert find_binding_conflicts(bindings) == ["p1_up"]


def test_esc_comparison_ignores_case():
    bindings = {"p1_up": "w", "p1_down": "s", "p2_up": "Escape", "p2_down": "down"}
    assert find_binding_conflicts(bindings) == ["p2_up"]


def test_esc_is_reported_with_other_conflicts():
    bindings = {"p1_up": "escape", "p1_down": "escape", "p2_up": "w", "p2_down": "w"}
    assert find_binding_conflicts(bindings) == [
        "p1_down",
        "p1_up",
        "p2_down",
        "p2_up",
    ]


def test_result_is_sorted_regardless_of_input_order():
    bindings = {"p2_up": "x", "p2_down": "x", "p1_up": "x", "p1_down": "q"}
    assert find_binding_conflicts(bindings) == ["p1_up", "p2_down", "p2_up"]
    reordered = {"p1_up": "x", "p2_up": "x", "p2_down": "x", "p1_down": "q"}
    assert find_binding_conflicts(reordered) == find_binding_conflicts(bindings)


def test_missing_action_raises_value_error():
    bindings = {"p1_up": "w", "p1_down": "s", "p2_up": "up"}
    with pytest.raises(ValueError):
        find_binding_conflicts(bindings)


def test_extra_action_raises_value_error():
    bindings = {
        "p1_up": "w",
        "p1_down": "s",
        "p2_up": "up",
        "p2_down": "down",
        "pause": "escape",
    }
    with pytest.raises(ValueError):
        find_binding_conflicts(bindings)


def test_unknown_action_name_raises_value_error():
    bindings = {"p1_up": "w", "p1_down": "s", "p2_up": "up", "p3_up": "down"}
    with pytest.raises(ValueError):
        find_binding_conflicts(bindings)
