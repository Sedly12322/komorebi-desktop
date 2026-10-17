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

