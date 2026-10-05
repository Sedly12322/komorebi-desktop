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
