import pytest
from wallhaven.pfps import PfpItem, format_download_count


def test_format_download_count():
    assert format_download_count(0) == "0"
    assert format_download_count(542) == "542"
    assert format_download_count(1200) == "1.2k"
    assert format_download_count(45600) == "45.6k"
    assert format_download_count(1000000) == "1.0M"
    assert format_download_count(2500000) == "2.5M"

    # String inputs
    assert format_download_count("1200") == "1.2k"
    assert format_download_count("45,600") == "45.6k"
    assert format_download_count("1,500,000") == "1.5M"
    assert format_download_count("unknown") == "unknown"
    assert format_download_count(None) == "0"


def test_pfp_item_properties():
    item = PfpItem(
        id="12345",
        title="Lofi Girl / Cat (Cute)",
        image_url="https://pfps.gg/assets/pfps/12345-lofi.png",
        format="png",
        downloads="1500",
        category="anime",
    )
    assert item.url == "https://pfps.gg/assets/pfps/12345-lofi.png"
    assert item.is_animated is False
    # Filename sanitization should replace slashes and spaces with underscores
    assert item.filename == "Lofi_Girl___Cat__Cute__12345.png"

    # Animated GIF item
    gif_item = PfpItem(
        id="67890",
        title="Cyberpunk Glitch",
        image_url="https://pfps.gg/assets/pfps/67890-glitch.gif",
        format="gif",
        downloads="8500",
    )
    assert gif_item.is_animated is True
    assert gif_item.filename.endswith(".gif")
