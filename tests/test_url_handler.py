"""Tests for URL handling safety helpers."""

from handlers.url_handler import UrlHandlerMixin


class Handler(UrlHandlerMixin):
    def __init__(self):
        self._x_cache = {}
        self._x_cache_settings = {"max_size": 2}


def test_url_classification_blacklists_and_title_filtering():
    handler = Handler()
    assert handler._is_youtube_url("https://youtu.be/abc")
    assert handler._is_youtube_url("https://youtube-nocookie.com/embed/abc")
    assert not handler._is_youtube_url("https://example.com")
    assert handler._is_x_url("https://x.com/user/status/123")
    assert handler._is_x_url("https://twitter.com/user/status/123")
    assert not handler._is_x_url("https://x.com/user")
    assert handler._is_url_blacklisted("http://localhost/page")
    assert handler._is_url_blacklisted("https://example.com/file.PDF")
    assert not handler._is_url_blacklisted("https://example.com/article")
    assert handler._is_title_banned("")
    assert handler._is_title_banned("Click here to buy now")
    assert not handler._is_title_banned("A useful article")


def test_x_response_cache_retrieves_and_discards_old_entries():
    handler = Handler()
    handler._cache_x_response("one", "first")
    assert handler._get_cached_x_response("one")["response"] == "first"
    assert handler._get_cached_x_response("missing") is None
    handler._cache_x_response("two", "second")
    handler._cache_x_response("three", "third")
    assert len(handler._x_cache) <= 2
    handler._manage_x_cache_size({})
