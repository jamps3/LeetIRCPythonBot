"""Tests for the TMDB-backed movie search service."""

from unittest.mock import Mock, patch

import requests

from services.imdb_service import MovieSearchService, create_imdb_service


def make_service():
    with patch.dict("os.environ", {"TMDB_API_KEY": "key"}):
        return MovieSearchService()


def test_service_initialization_and_factory():
    with patch.dict("os.environ", {}, clear=True):
        assert MovieSearchService().api_key == ""
    with patch.dict("os.environ", {"TMDB_API_KEY": "key"}):
        assert isinstance(create_imdb_service(), MovieSearchService)


def test_search_movie_validates_configuration_and_query():
    with patch.dict("os.environ", {}, clear=True):
        assert (
            MovieSearchService().search_movie("Alien")["message"]
            == "TMDB API key not configured"
        )
    assert make_service().search_movie("  ")["message"] == "Empty search query"


def test_search_movie_returns_detailed_result():
    search = Mock(status_code=200)
    search.json.return_value = {"results": [{"id": 1, "title": "Fallback"}]}
    details = Mock(status_code=200)
    details.json.return_value = {
        "title": "Alien",
        "release_date": "1979-05-25",
        "imdb_id": "tt0078748",
        "overview": "x" * 201,
        "vote_average": 8.42,
    }
    with patch("services.imdb_service.requests.get", side_effect=[search, details]):
        result = make_service().search_movie(" Alien ")

    assert result["title"] == "Alien"
    assert result["year"] == "1979"
    assert result["imdb_url"].endswith("tt0078748/")
    assert result["overview"].endswith("...")
    assert result["rating"] == "8.4/10"


def test_search_movie_falls_back_to_search_result():
    search = Mock(status_code=200)
    search.json.return_value = {
        "results": [
            {
                "id": 2,
                "title": "Basic",
                "release_date": "",
                "overview": "short",
                "vote_average": 0,
            }
        ]
    }
    details = Mock(status_code=500)
    with patch("services.imdb_service.requests.get", side_effect=[search, details]):
        result = make_service().search_movie("Basic")

    assert result == {
        "error": False,
        "title": "Basic",
        "year": "",
        "tmdb_url": "https://www.themoviedb.org/movie/2",
        "overview": "short",
        "rating": "",
    }


def test_search_movie_handles_api_and_request_errors():
    service = make_service()
    response = Mock(status_code=503)
    with patch("services.imdb_service.requests.get", return_value=response):
        assert "503" in service.search_movie("Alien")["message"]

    response = Mock(status_code=200)
    response.json.return_value = {"results": []}
    with patch("services.imdb_service.requests.get", return_value=response):
        assert "No movies" in service.search_movie("Alien")["message"]

    with patch(
        "services.imdb_service.requests.get", side_effect=requests.exceptions.Timeout
    ):
        assert "timed out" in service.search_movie("Alien")["message"]
    with patch(
        "services.imdb_service.requests.get",
        side_effect=requests.exceptions.RequestException("offline"),
    ):
        assert "offline" in service.search_movie("Alien")["message"]
    with patch("services.imdb_service.requests.get", side_effect=ValueError("bad")):
        assert "Unexpected error" in service.search_movie("Alien")["message"]


def test_format_movie_info_variants():
    service = make_service()
    assert "error: nope" in service.format_movie_info(
        {"error": True, "message": "nope"}
    )
    assert (
        service.format_movie_info(
            {"title": "Alien", "year": "1979", "rating": "8.4/10", "imdb_url": "imdb"}
        )
        == "🎬 Alien (1979) - 8.4/10 - imdb (themoviedb.org)"
    )
    assert "tmdb" in service.format_movie_info({"title": "Basic", "tmdb_url": "tmdb"})
