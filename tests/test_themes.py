import re
import pytest
from wallhaven.styles import THEME_PALETTES, get_palette, get_available_themes
from wallhaven.config import DEFAULT_CONFIG, config


def test_default_config_values():
    assert DEFAULT_CONFIG["language"] == "en"
    assert DEFAULT_CONFIG["auto_set_wallpaper"] is False


def test_custom_themes_present():
    expected_custom_themes = ["rose_pine", "everforest", "kanagawa", "synthwave"]
    for theme_id in expected_custom_themes:
        assert theme_id in THEME_PALETTES, f"Theme {theme_id} is missing from THEME_PALETTES"


def test_theme_palettes_completeness():
    required_keys = {
        "name",
        "bg_base",
        "bg_surface",
        "bg_subsurface",
        "bg_capsule",
        "bg_input",
        "bg_input_hover",
        "bg_card_hover",
        "border",
        "border_subtle",
        "border_hover",
        "accent",
        "accent_hover",
        "accent_gradient_start",
        "accent_gradient_end",
        "accent_surface",
        "accent_text",
        "text_primary",
        "text_secondary",
        "text_muted",
    }
    hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")

    for theme_id, pal in THEME_PALETTES.items():
        missing = required_keys - set(pal.keys())
        assert not missing, f"Theme {theme_id} is missing keys: {missing}"

        # Verify all color values except 'name' are valid 6-char hex strings
        for k, v in pal.items():
            if k == "name":
                assert isinstance(v, str) and len(v) > 0
            else:
                assert hex_pattern.match(v), f"Theme {theme_id} has invalid hex color for {k}: {v}"


def test_dark_theme_preserved_on_load(tmp_path, monkeypatch):
    import json
    import wallhaven.config as cfg_mod

    fake_cfg_dir = tmp_path / "config"
    fake_cfg_file = fake_cfg_dir / "config.json"
    fake_cfg_dir.mkdir(parents=True)
    fake_cfg_file.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", fake_cfg_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", fake_cfg_file)

    c = cfg_mod.Config()
    assert c.theme == "dark"


def test_wallpaper_placeholder_substitution():
    from wallhaven.wallpaper import _substitute_file_placeholder

    path_with_quotes = "/home/user/Pictures/It's a wallpaper.jpg"
    res1 = _substitute_file_placeholder("swww img '{file}'", path_with_quotes)
    assert "It" in res1 and "{file}" not in res1

    res2 = _substitute_file_placeholder("feh --bg-fill {file}", path_with_quotes)
    assert "{file}" not in res2


def test_apply_specific_setter_recognizes_awww_and_hypr_script(monkeypatch, tmp_path):
    import shutil
    from wallhaven.wallpaper import _apply_specific_setter

    monkeypatch.setattr(shutil, "which", lambda name: None)
    ok, msg = _apply_specific_setter("awww", "/tmp/fake.jpg", False)
    assert ok is False
    assert "unknown" not in msg.lower()


def test_i18n_keys_parity():
    from wallhaven.i18n import TRANSLATIONS

    en_keys = set(TRANSLATIONS["en"].keys())
    cs_keys = set(TRANSLATIONS["cs"].keys())
    assert en_keys == cs_keys, f"Mismatched i18n keys: EN-only={en_keys - cs_keys}, CS-only={cs_keys - en_keys}"


def test_multi_monitor_detection_and_placeholder(monkeypatch):
    import shutil
    from wallhaven.wallpaper import (
        get_available_monitors,
        _substitute_file_placeholder,
        detect_wallpaper_command,
    )

    monitors = get_available_monitors()
    assert len(monitors) >= 1
    assert monitors[0][0] == "all"

    res = _substitute_file_placeholder("swww img -o {monitor} '{file}'", "/tmp/wall.jpg", monitor="DP-1")
    assert "DP-1" in res
    assert "/tmp/wall.jpg" in res

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/awww" if name == "awww" else None)
    cmd_all = detect_wallpaper_command(for_video=False, monitor="all")
    assert "-o" not in cmd_all
    cmd_dp1 = detect_wallpaper_command(for_video=False, monitor="DP-1")
    assert "-o" in cmd_dp1 and "DP-1" in cmd_dp1




def test_terminal_palettes_and_anim_helpers(tmp_path):
    from wallhaven.styles import THEME_PALETTES
    from wallhaven.animated_preview import _DecodeThread, ensure_local_video, resolve_animated_source

    assert "terminal" in THEME_PALETTES
    t = _DecodeThread("x", (284, 172), cover=True)
    w, h = t._target_size(1280, 720)
    assert w >= 284 and h >= 172 and w % 2 == 0 and h % 2 == 0
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    assert ensure_local_video(str(f)) == str(f)

    class It:
        local_path = str(f)

    assert resolve_animated_source(It()) == str(f)
