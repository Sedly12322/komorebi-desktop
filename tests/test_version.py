import pytest
from wallhaven.updater import parse_semver, is_newer_version


def test_parse_semver():
    assert parse_semver("2.0.0") == (2, 0, 0)
    assert parse_semver("v2.1.3") == (2, 1, 3)
    assert parse_semver("V1.0.0-rc1") == (1, 0, 0)
    assert parse_semver("1.4") == (1, 4, 0)
    assert parse_semver("3") == (3, 0, 0)
    assert parse_semver("") == (0, 0, 0)


def test_is_newer_version():
    # Newer
    assert is_newer_version("2.0.1", "2.0.0") is True
    assert is_newer_version("v2.1.0", "2.0.9") is True
    assert is_newer_version("3.0.0", "2.9.9") is True

    # Same version
    assert is_newer_version("2.0.0", "2.0.0") is False
    assert is_newer_version("v2.0.0", "2.0.0") is False

    # Older version
    assert is_newer_version("1.9.9", "2.0.0") is False
    assert is_newer_version("2.0.0", "2.0.1") is False
