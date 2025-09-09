import types
from datetime import datetime, timedelta

import pytest
import requests

from services.youtube_service import YouTubeService, create_youtube_service


class DummyResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


@pytest.fixture()
def svc():
    return YouTubeService(api_key="TEST_KEY")


# ----------------------- extract_video_id -----------------------


def test_extract_video_id_variants(svc):
    urls = [
        "https://www.youtube.com/watch?v=ABCDEFGHIJK",
        "https://youtu.be/ABCDEFGHIJK",
        "https://www.youtube.com/embed/ABCDEFGHIJK",
        "https://www.youtube.com/v/ABCDEFGHIJK",
    ]
    for u in urls:
        assert svc.extract_video_id(u) == "ABCDEFGHIJK"

    assert svc.extract_video_id("no youtube here") is None


# ----------------------- get_video_info -----------------------


def test_get_video_info_success(monkeypatch, svc):
    data = {
        "items": [
            {
                "snippet": {
                    "title": "Test Title",
                    "channelTitle": "Chan",
                    "description": "Desc",
                    "publishedAt": "2023-01-02T03:04:05Z",
                },
                "statistics": {
                    "viewCount": "1234567",
                    "likeCount": "2345",
                    "commentCount": "10",
                },
                "contentDetails": {"duration": "PT1H2M3S"},
            }
        ]
    }

    monkeypatch.setattr(
        requests, "get", lambda url, params=None, timeout=10: DummyResponse(200, data)
    )

    res = svc.get_video_info("ABCDEFGHIJK")
    assert not res["error"]
    assert res["title"] == "Test Title"
    assert res["duration"] == "1:02:03"
    assert isinstance(res["upload_date"], datetime)


def test_get_video_info_not_found(monkeypatch, svc):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: DummyResponse(200, {"items": []})
    )
    res = svc.get_video_info("ID")
    assert res["error"] and "Video not found" in res["message"]


def test_get_video_info_non_200(monkeypatch, svc):
    monkeypatch.setattr(requests, "get", lambda *a, **k: DummyResponse(403, {}))
    res = svc.get_video_info("ID")
    assert res["error"] and res["status_code"] == 403


def test_get_video_info_timeout(monkeypatch, svc):
    def _raise_timeout(*a, **k):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(requests, "get", _raise_timeout)
    res = svc.get_video_info("ID")
    assert res["error"] and res["exception"] == "timeout"


def test_get_video_info_request_exception(monkeypatch, svc):
    def _raise_req(*a, **k):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr(requests, "get", _raise_req)
    res = svc.get_video_info("ID")
    assert res["error"] and "boom" in res["message"]


def test_get_video_info_unexpected_exception(monkeypatch, svc):
    def _raise_other(*a, **k):
        raise Exception("oops")

    monkeypatch.setattr(requests, "get", _raise_other)
    res = svc.get_video_info("ID")
    assert res["error"] and "Unexpected error" in res["message"]


def test_parse_video_data_duration_and_invalid(monkeypatch, svc):
    # Valid duration
    data_valid = {
        "items": [
            {
                "snippet": {
                    "title": "T",
                    "channelTitle": "C",
                    "publishedAt": "2023-01-01T00:00:00Z",
                },
                "statistics": {"viewCount": "1", "likeCount": "2", "commentCount": "3"},
                "contentDetails": {"duration": "PT3M5S"},
            }
        ]
    }
    res1 = svc._parse_video_data(data_valid, "VID")
    assert res1["duration"] == "3:05"

    # Invalid duration string -> Unknown, but still no error
    data_invalid_dur = {
        "items": [
            {
                "snippet": {"title": "T", "channelTitle": "C"},
                "statistics": {"viewCount": "1", "likeCount": "2", "commentCount": "3"},
                "contentDetails": {"duration": "nonsense"},
            }
        ]
    }
    res2 = svc._parse_video_data(data_invalid_dur, "VID")
    assert not res2["error"] and res2["duration"] == "Unknown"

    # Force parse error (non-int viewCount)
    data_bad_stats = {
        "items": [
            {
                "snippet": {"title": "T", "channelTitle": "C"},
                "statistics": {"viewCount": "notanint"},
                "contentDetails": {"duration": "PT1S"},
            }
        ]
    }
    res3 = svc._parse_video_data(data_bad_stats, "VID")
    assert res3["error"] and "Error parsing video data" in res3["message"]

    # Bad publishedAt to hit upload_date except branch -> None but no error
    data_bad_date = {
        "items": [
            {
                "snippet": {
                    "title": "T",
                    "channelTitle": "C",
                    "publishedAt": "bad-date",
                },
                "statistics": {"viewCount": "1", "likeCount": "2", "commentCount": "3"},
                "contentDetails": {"duration": "PT1M"},
            }
        ]
    }
    res4 = svc._parse_video_data(data_bad_date, "VID")
    assert not res4["error"] and res4["upload_date"] is None


# ----------------------- search_videos -----------------------


def test_search_videos_success_and_formatting(monkeypatch, svc):
    items = []
    for i in range(5):
        items.append(
            {
                "id": {"videoId": f"VID{i}"},
                "snippet": {
                    "title": f"Title {i}",
                    "channelTitle": f"Chan{i}",
                    "description": "desc",
                    "publishedAt": "2023-01-02T03:04:05Z",
                },
            }
        )

    monkeypatch.setattr(
        requests, "get", lambda *a, **k: DummyResponse(200, {"items": items})
    )

    res = svc.search_videos("query", max_results=7)
    assert not res["error"] and res["total_results"] == 5

    # Formatting: more than 3 should add trailing line
    msg = svc.format_search_results_message(res)
    assert "YouTube search results for 'query'" in msg
    assert "... and 2 more results" in msg


def test_search_videos_non_200(monkeypatch, svc):
    monkeypatch.setattr(requests, "get", lambda *a, **k: DummyResponse(500, {}))
    res = svc.search_videos("q")
    assert res["error"] and res["status_code"] == 500


def test_search_videos_timeout(monkeypatch, svc):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.Timeout()),
    )
    res = svc.search_videos("q")
    assert res["error"] and res["exception"] == "timeout"


def test_search_videos_request_exception(monkeypatch, svc):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **k: (_ for _ in ()).throw(
            requests.exceptions.RequestException("xx")
        ),
    )
    res = svc.search_videos("q")
    assert res["error"] and "xx" in res["message"]


def test_search_videos_unexpected(monkeypatch, svc):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: (_ for _ in ()).throw(Exception("e"))
    )
    res = svc.search_videos("q")
    assert res["error"] and "Error searching YouTube" in res["message"]


def test_parse_search_results_error_path(svc):
    # items list has a non-dict so .get will raise
    res = svc._parse_search_results({"items": [1]}, "q")
    assert res["error"] and "Error parsing search results" in res["message"]


def test_parse_search_results_bad_published_at_sets_none(svc):
    data = {
        "items": [
            {
                "id": {"videoId": "VID"},
                "snippet": {
                    "title": "T",
                    "channelTitle": "C",
                    "description": "",
                    "publishedAt": "bad-date",
                },
            }
        ]
    }
    res = svc._parse_search_results(data, "q")
    assert not res["error"] and res["results"][0]["upload_date"] is None


# ----------------------- formatting helpers -----------------------


def test_format_video_info_message_variants(svc):
    # Error path
    assert "YouTube error" in svc.format_video_info_message(
        {"error": True, "message": "m"}
    )

    # Views and likes formatting branches
    base = {
        "error": False,
        "video_id": "VID",
        "title": "T",
        "channel": "C",
        "duration": "3:05",
        "comment_count": 0,
        "description": "",
        "tags": [],
        "url": "https://www.youtube.com/watch?v=VID",
    }

    msg1 = svc.format_video_info_message(
        {**base, "view_count": 999, "like_count": 999, "upload_date": None}
    )
    assert "999|999👍" in msg1 and "Unknown" in msg1

    msg2 = svc.format_video_info_message(
        {
            **base,
            "view_count": 1500,
            "like_count": 1500,
            "upload_date": datetime(2023, 1, 1),
        }
    )
    assert "1.5k|1.5k👍" in msg2 and "01.01.2023" in msg2

    msg3 = svc.format_video_info_message(
        {
            **base,
            "view_count": 2_000_000,
            "like_count": 3_000_000,
            "upload_date": datetime(2023, 2, 2),
        }
    )
    assert "2.0M|3.0M👍" in msg3 and "02.02.2023" in msg3


def test_format_search_results_message_variants(svc):
    # Error path
    assert "YouTube search error" in svc.format_search_results_message(
        {"error": True, "message": "m"}
    )

    # No results
    assert "No YouTube videos found" in svc.format_search_results_message(
        {"error": False, "query": "q", "results": []}
    )

    # <=3 results
    res = {
        "error": False,
        "query": "q",
        "results": [
            {"title": "t1", "channel": "c1", "url": "u1"},
            {"title": "t2", "channel": "c2", "url": "u2"},
        ],
    }
    msg = svc.format_search_results_message(res)
    assert "1. 't1'" in msg and "2. 't2'" in msg and "more results" not in msg


# ----------------------- _format_duration and factory -----------------------


def test_format_duration_and_factory(svc):
    # minutes only
    assert svc._format_duration(timedelta(seconds=65)) == "1:05"
    # hours branch
    assert svc._format_duration(timedelta(hours=1, minutes=1, seconds=1)) == "1:01:01"

    # factory
    new_svc = create_youtube_service("K")
    assert isinstance(new_svc, YouTubeService)
