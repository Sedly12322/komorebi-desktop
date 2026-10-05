import pytest
from wallhaven.api import WallpaperItem, SearchResult


def test_wallpaper_item_from_dict():
    raw_dict = {
        "id": "abc123",
        "url": "https://wallhaven.cc/w/abc123",
        "short_url": "https://whvn.cc/abc123",
        "views": 4200,
        "favorites": 150,
        "source": "https://example.com/art",
        "purity": "sfw",
        "category": "anime",
        "dimension_x": 3840,
        "dimension_y": 2160,
        "resolution": "3840x2160",
        "ratio": "16:9",
        "file_size": 5242880,
        "file_type": "image/jpeg",
        "created_at": "2026-01-01 12:00:00",
        "colors": ["#000000", "#ffffff"],
        "path": "https://w.wallhaven.cc/full/ab/wallhaven-abc123.jpg",
        "thumbs": {
            "large": "https://th.wallhaven.cc/lg/ab/abc123.jpg",
            "original": "https://th.wallhaven.cc/orig/ab/abc123.jpg",
            "small": "https://th.wallhaven.cc/sm/ab/abc123.jpg",
        },
        "tags": [{"id": 1, "name": "cyberpunk"}],
    }

    item = WallpaperItem.from_dict(raw_dict)
    assert item.id == "abc123"
    assert item.views == 4200
    assert item.favorites == 150
    assert item.resolution == "3840x2160"
    assert item.ratio == "16:9"
    assert item.thumb_large == "https://th.wallhaven.cc/lg/ab/abc123.jpg"
    assert item.is_animated is False
    assert len(item.tags) == 1
    assert item.tags[0]["name"] == "cyberpunk"


def test_search_result_creation():
    items = [
        WallpaperItem(
            id="1",
            url="https://wallhaven.cc/w/1",
            short_url="https://whvn.cc/1",
            views=10,
            favorites=2,
            source="",
            purity="sfw",
            category="general",
            dimension_x=1920,
            dimension_y=1080,
            resolution="1920x1080",
            ratio="16:9",
            file_size=1024,
            file_type="image/jpeg",
            created_at="",
            colors=[],
            path="",
            thumb_large="",
            thumb_small="",
            thumb_original="",
        )
    ]
    res = SearchResult(
        items=items,
        current_page=1,
        last_page=10,
        total=240,
        per_page=24,
    )
    assert len(res.items) == 1
    assert res.current_page == 1
    assert res.last_page == 10
    assert res.total == 240
