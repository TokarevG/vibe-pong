import ast
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from pong.ai import Difficulty
from pong.game import Mode
from pong.settings import (
    Settings,
    config_path,
    default_settings,
    find_binding_conflicts,
    load_settings,
    save_settings,
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


def _write_config(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_file() -> dict[str, object]:
    return {
        "mode": "two_player",
        "difficulty": "hard",
        "audio_enabled": False,
        "volume": 35,
        "bindings": {"p1_up": "i", "p1_down": "k", "p2_up": "o", "p2_down": "l"},
    }


def test_load_full_valid_file(tmp_path):
    path = _write_config(tmp_path / "config.json", _valid_file())
    settings = load_settings(path)
    assert settings.mode is Mode.TWO_PLAYER
    assert settings.difficulty is Difficulty.HARD
    assert settings.audio_enabled is False
    assert settings.volume == 35
    assert settings.bindings == {
        "p1_up": "i",
        "p1_down": "k",
        "p2_up": "o",
        "p2_down": "l",
    }


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("single_player", Mode.SINGLE_PLAYER), ("two_player", Mode.TWO_PLAYER)],
)
def test_load_mode_names(tmp_path, stored, expected):
    path = _write_config(tmp_path / "config.json", {"mode": stored})
    assert load_settings(path).mode is expected


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("easy", Difficulty.EASY),
        ("medium", Difficulty.MEDIUM),
        ("hard", Difficulty.HARD),
    ],
)
def test_load_difficulty_names(tmp_path, stored, expected):
    path = _write_config(tmp_path / "config.json", {"difficulty": stored})
    assert load_settings(path).difficulty is expected


def test_missing_file_returns_defaults(tmp_path):
    settings = load_settings(tmp_path / "does_not_exist.json")
    assert settings == default_settings()


def test_directory_path_returns_defaults(tmp_path):
    directory = tmp_path / "config.json"
    directory.mkdir()
    assert load_settings(directory) == default_settings()


def test_corrupt_json_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"volume": 40,', encoding="utf-8")
    assert load_settings(path) == default_settings()


def test_binary_data_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(bytes(range(256)) + b"\xff\xfe\x00\x81")
    assert load_settings(path) == default_settings()


def test_invalid_utf8_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'{"volume": 40, "name": "\xff"}')
    assert load_settings(path) == default_settings()


@pytest.mark.parametrize("content", [[], ["volume", 40], "loud", 42, None, True])
def test_top_level_non_object_returns_defaults(tmp_path, content):
    path = _write_config(tmp_path / "config.json", content)
    assert load_settings(path) == default_settings()


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"   ",
        b"\x00" * 16,
        "[" * 100_000 + "]" * 100_000,
        '{"volume": NaN, "mode": ',
    ],
)
def test_never_raises_for_odd_file_content(tmp_path, content):
    path = tmp_path / "config.json"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    assert load_settings(path) == default_settings()


@pytest.mark.parametrize("volume", ["loud", True, False, 50.0, 101, -1, None, [40]])
def test_invalid_volume_gets_default_only(tmp_path, volume):
    data = _valid_file() | {"volume": volume}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.volume == default_settings().volume
    assert settings.mode is Mode.TWO_PLAYER
    assert settings.bindings["p1_up"] == "i"


@pytest.mark.parametrize("volume", [0, 100, 1, 99])
def test_volume_bounds_are_accepted(tmp_path, volume):
    settings = load_settings(
        _write_config(tmp_path / "config.json", {"volume": volume})
    )
    assert settings.volume == volume


@pytest.mark.parametrize("audio", [1, 0, "true", "false", None, []])
def test_audio_enabled_must_be_a_json_boolean(tmp_path, audio):
    data = _valid_file() | {"audio_enabled": audio}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.audio_enabled is default_settings().audio_enabled
    assert settings.volume == 35


@pytest.mark.parametrize("mode", ["Two_Player", "solo", 2, None, ["two_player"]])
def test_invalid_mode_gets_default_only(tmp_path, mode):
    data = _valid_file() | {"mode": mode}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.mode is default_settings().mode
    assert settings.difficulty is Difficulty.HARD


@pytest.mark.parametrize("difficulty", ["expert", "EASY", 1, None, ["hard"]])
def test_invalid_difficulty_gets_default_only(tmp_path, difficulty):
    data = _valid_file() | {"difficulty": difficulty}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.difficulty is default_settings().difficulty
    assert settings.mode is Mode.TWO_PLAYER


def test_wrong_types_across_fields_keep_valid_ones(tmp_path):
    data = {"volume": "loud", "audio_enabled": 1, "mode": "two_player"}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.volume == 80
    assert settings.audio_enabled is True
    assert settings.mode is Mode.TWO_PLAYER


def test_partly_valid_file_keeps_valid_fields(tmp_path):
    data = {"difficulty": "easy", "volume": 101, "bindings": {"p1_up": "i"}}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.difficulty is Difficulty.EASY
    assert settings.volume == 80
    assert settings.mode is Mode.SINGLE_PLAYER
    assert settings.bindings == {
        "p1_up": "i",
        "p1_down": "s",
        "p2_up": "up",
        "p2_down": "down",
    }


@pytest.mark.parametrize("missing", ["p1_up", "p1_down", "p2_up", "p2_down"])
def test_missing_action_gets_its_default(tmp_path, missing):
    custom = {"p1_up": "i", "p1_down": "k", "p2_up": "o", "p2_down": "l"}
    del custom[missing]
    data = {"bindings": custom, "volume": 10}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    expected = default_settings().bindings[missing]
    assert settings.bindings[missing] == expected
    for action, key in custom.items():
        assert settings.bindings[action] == key
    assert settings.volume == 10


@pytest.mark.parametrize("bad", [5, None, True, ["w"], {"key": "w"}, "", 1.5])
def test_non_string_or_empty_binding_gets_its_default(tmp_path, bad):
    bindings = {"p1_up": "i", "p1_down": "k", "p2_up": "o", "p2_down": bad}
    data = {"bindings": bindings}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.bindings == {
        "p1_up": "i",
        "p1_down": "k",
        "p2_up": "o",
        "p2_down": "down",
    }


@pytest.mark.parametrize("bindings", ["w", 3, None, ["w", "s"]])
def test_bindings_not_an_object_gets_defaults(tmp_path, bindings):
    data = _valid_file() | {"bindings": bindings}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.bindings == default_settings().bindings
    assert settings.mode is Mode.TWO_PLAYER


def test_conflicting_bindings_reset_all_four_to_defaults(tmp_path):
    bindings = {"p1_up": "w", "p1_down": "w", "p2_up": "up", "p2_down": "down"}
    data = {"bindings": bindings, "volume": 20}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.bindings == default_settings().bindings
    assert settings.volume == 20


def test_escape_binding_resets_all_four_to_defaults(tmp_path):
    bindings = {"p1_up": "i", "p1_down": "k", "p2_up": "escape", "p2_down": "l"}
    data = {"bindings": bindings}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.bindings == default_settings().bindings


def test_conflict_check_is_case_insensitive(tmp_path):
    bindings = {"p1_up": "W", "p1_down": "s", "p2_up": "w", "p2_down": "down"}
    data = {"bindings": bindings}
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.bindings == default_settings().bindings


def test_conflict_reset_does_not_touch_other_fields(tmp_path):
    data = _valid_file() | {
        "bindings": {"p1_up": "w", "p1_down": "w", "p2_up": "up", "p2_down": "down"}
    }
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings.bindings == default_settings().bindings
    assert settings.mode is Mode.TWO_PLAYER
    assert settings.volume == 35


def test_unknown_extra_keys_are_ignored(tmp_path):
    data = _valid_file() | {
        "theme": "neon",
        "bindings": _valid_file()["bindings"] | {"pause": "p"},
    }
    settings = load_settings(_write_config(tmp_path / "config.json", data))
    assert settings == load_settings(
        _write_config(tmp_path / "plain.json", _valid_file())
    )
    assert not hasattr(settings, "theme")
    assert "pause" not in settings.bindings


def test_load_returns_a_new_object_each_call(tmp_path):
    path = _write_config(tmp_path / "config.json", _valid_file())
    first = load_settings(path)
    first.bindings["p1_up"] = "x"
    assert load_settings(path).bindings["p1_up"] == "i"
    assert load_settings(tmp_path / "missing.json").bindings["p1_up"] == "w"


def _custom_settings() -> Settings:
    return Settings(
        mode=Mode.TWO_PLAYER,
        difficulty=Difficulty.HARD,
        audio_enabled=False,
        volume=35,
        bindings={"p1_up": "i", "p1_down": "k", "p2_up": "o", "p2_down": "l"},
    )


def _config_files(directory: Path) -> list[str]:
    return sorted(entry.name for entry in directory.iterdir())


def test_save_returns_true_and_writes_the_file(tmp_path):
    path = tmp_path / "config.json"
    assert save_settings(path, _custom_settings()) is True
    assert path.is_file()


def test_save_creates_missing_parent_directories(tmp_path):
    path = tmp_path / "missing" / "nested" / "pong" / "config.json"
    assert save_settings(path, default_settings()) is True
    assert path.is_file()
    assert load_settings(path) == default_settings()


def test_save_uses_the_same_field_names_and_value_formats_as_load(tmp_path):
    path = tmp_path / "config.json"
    save_settings(path, _custom_settings())
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "mode": "two_player",
        "difficulty": "hard",
        "audio_enabled": False,
        "volume": 35,
        "bindings": {"p1_up": "i", "p1_down": "k", "p2_up": "o", "p2_down": "l"},
    }


def test_save_writes_single_player_and_easy_names(tmp_path):
    path = tmp_path / "config.json"
    save_settings(path, default_settings())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mode"] == "single_player"
    assert data["difficulty"] == "medium"


@pytest.mark.parametrize(
    "settings",
    [
        default_settings(),
        _custom_settings(),
        Settings(mode=Mode.SINGLE_PLAYER, difficulty=Difficulty.EASY, volume=0),
        Settings(volume=100, audio_enabled=False),
        Settings(
            bindings={"p1_up": "W", "p1_down": "a", "p2_up": "up", "p2_down": "x"}
        ),
    ],
)
def test_round_trip_returns_an_equal_settings(tmp_path, settings):
    path = tmp_path / "config.json"
    assert save_settings(path, settings) is True
    assert load_settings(path) == settings


def test_save_overwrites_an_existing_file(tmp_path):
    path = _write_config(tmp_path / "config.json", {"volume": 5})
    save_settings(path, _custom_settings())
    assert load_settings(path) == _custom_settings()


def test_save_leaves_no_temporary_files_behind(tmp_path):
    path = tmp_path / "config.json"
    save_settings(path, _custom_settings())
    assert _config_files(tmp_path) == ["config.json"]


def _bad(**fields: Any) -> Settings:
    """Build a Settings with deliberately wrong field types for invalid-input tests."""
    return Settings(**fields)


@pytest.mark.parametrize(
    "settings",
    [
        _bad(volume=101),
        _bad(volume=-1),
        _bad(volume=True),
        _bad(volume=50.0),
        _bad(volume="80"),
        _bad(audio_enabled=1),
        _bad(audio_enabled="yes"),
        _bad(mode="two_player"),
        _bad(mode=2),
        _bad(difficulty="hard"),
        _bad(difficulty=None),
        _bad(bindings={"p1_up": "w", "p1_down": "w", "p2_up": "up", "p2_down": "down"}),
        _bad(
            bindings={
                "p1_up": "escape",
                "p1_down": "s",
                "p2_up": "up",
                "p2_down": "down",
            }
        ),
        _bad(bindings={"p1_up": "w", "p1_down": "s", "p2_up": "up"}),
        _bad(
            bindings={
                "p1_up": "w",
                "p1_down": "s",
                "p2_up": "up",
                "pause": "x",
                "p2_down": "down",
            }
        ),
        _bad(bindings={"p1_up": "", "p1_down": "s", "p2_up": "up", "p2_down": "down"}),
        _bad(bindings={"p1_up": 5, "p1_down": "s", "p2_up": "up", "p2_down": "down"}),
        _bad(bindings=None),
    ],
)
def test_invalid_settings_raise_value_error_and_write_nothing(tmp_path, settings):
    path = tmp_path / "new_dir" / "config.json"
    with pytest.raises(ValueError):
        save_settings(path, settings)
    assert not (tmp_path / "new_dir").exists()


def test_invalid_settings_leave_an_existing_file_untouched(tmp_path):
    path = _write_config(tmp_path / "config.json", _valid_file())
    before = path.read_bytes()
    with pytest.raises(ValueError):
        save_settings(path, Settings(volume=500))
    assert path.read_bytes() == before
    assert _config_files(tmp_path) == ["config.json"]


def test_failed_write_keeps_the_old_file_and_removes_temp_file(tmp_path, monkeypatch):
    path = _write_config(tmp_path / "config.json", _valid_file())
    before = path.read_bytes()

    def fail_replace(self, target):
        raise OSError("disk trouble")

    monkeypatch.setattr(Path, "replace", fail_replace)
    assert save_settings(path, _custom_settings()) is False
    assert path.read_bytes() == before
    assert _config_files(tmp_path) == ["config.json"]


def test_failed_write_does_not_create_a_partial_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"

    def fail_replace(self, target):
        raise OSError("disk trouble")

    monkeypatch.setattr(Path, "replace", fail_replace)
    assert save_settings(path, _custom_settings()) is False
    assert not path.exists()
    assert _config_files(tmp_path) == []


def test_unwritable_location_returns_false_and_does_not_raise(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    path = blocker / "config.json"
    assert save_settings(path, default_settings()) is False


def test_target_that_is_a_directory_returns_false(tmp_path):
    path = tmp_path / "config.json"
    path.mkdir()
    assert save_settings(path, default_settings()) is False
    assert _config_files(tmp_path) == ["config.json"]


def test_save_does_not_change_the_settings_object(tmp_path):
    settings = _custom_settings()
    before = Settings(
        mode=settings.mode,
        difficulty=settings.difficulty,
        audio_enabled=settings.audio_enabled,
        volume=settings.volume,
        bindings=dict(settings.bindings),
    )
    save_settings(tmp_path / "config.json", settings)
    assert settings == before
