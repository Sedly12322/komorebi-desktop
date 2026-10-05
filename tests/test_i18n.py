import pytest
from wallhaven.i18n import i18n, tr, TRANSLATIONS


def test_tr_lookup_and_format():
    i18n.set_language("en")
    assert tr("btn_save") == "Save"
    assert tr("btn_cancel") == "Cancel"
    assert tr("page_info", current=1, last=5) == "Page 1 of 5"

    i18n.set_language("cs")
    assert tr("btn_save") == "Uložit"
    assert tr("btn_cancel") == "Zrušit"
    assert tr("page_info", current=1, last=5) == "Strana 1 z 5"


def test_critical_keys_exist_in_all_languages():
    en_keys = set(TRANSLATIONS["en"].keys())
    cs_keys = set(TRANSLATIONS["cs"].keys())

    # Critical keys that must exist in both languages
    critical = [
        "app_title",
        "btn_save",
        "btn_cancel",
        "settings_title",
        "search_button",
        "update_section",
        "updater_prog_verifying_hash",
        "updater_err_sha256_mismatch",
        "ratio_any",
        "theme_matugen",
        "theme_gtk",
        "theme_kde",
        "theme_accent",
        "theme_pywal",
        "setter_desc_win_api",
        "setter_desc_win_lively",
    ]

    for key in critical:
        assert key in en_keys, f"Missing English translation for: {key}"
        assert key in cs_keys, f"Missing Czech translation for: {key}"
