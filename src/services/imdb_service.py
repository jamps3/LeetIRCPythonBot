"""
Movie Search Service Module

Provides movie search functionality using TMDB API (The Movie Database).
IMDb scraping has been discontinued due to anti-bot protection.
"""

import os
from typing import Dict

import requests

from logger import get_logger

logger = get_logger("MovieSearchService")


class MovieSearchService:
    """Service for searching movies using TMDB API."""

    def __init__(self):
        """Initialize movie search service."""
        self.base_url = "https://api.themoviedb.org/3"
        self.api_key = os.getenv("TMDB_API_KEY", "")
        if not self.api_key:
            logger.warning("TMDB_API_KEY not set - movie search will not work")

    def search_movie(self, query: str) -> Dict[str, str]:
        """
        Search for a movie using TMDB API.

        Args:
            query: Movie title to search for

        Returns:
            Dictionary containing movie info or error details
        """
        try:
            if not self.api_key:
                return {"error": True, "message": "TMDB API key not configured"}

            # Clean and prepare the query
            query = query.strip()
            if not query:
                return {"error": True, "message": "Empty search query"}

            # TMDB search endpoint
            search_url = f"{self.base_url}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": query,
                "language": "en-US",
                "page": 1,
            }

            response = requests.get(search_url, params=params, timeout=10)

            if response.status_code != 200:
                return {
                    "error": True,
                    "message": f"TMDB API returned status code {response.status_code}",
                }

            data = response.json()

            if not data.get("results"):
                return {"error": True, "message": f"No movies found for '{query}'"}

            # Get the first (best) result
            movie = data["results"][0]

            # Get detailed movie info
            movie_id = movie["id"]
            details_url = f"{self.base_url}/movie/{movie_id}"
            details_params = {"api_key": self.api_key, "language": "en-US"}

            details_response = requests.get(
                details_url, params=details_params, timeout=10
            )

            if details_response.status_code == 200:
                movie_details = details_response.json()

                return {
                    "error": False,
                    "title": movie_details.get("title", movie.get("title", "Unknown")),
                    "year": (
                        movie_details.get("release_date", "")[:4]
                        if movie_details.get("release_date")
                        else ""
                    ),
                    "imdb_url": (
                        f"https://www.imdb.com/title/{movie_details.get('imdb_id')}/"
                        if movie_details.get("imdb_id")
                        else ""
                    ),
                    "tmdb_url": f"https://www.themoviedb.org/movie/{movie_id}",
                    "overview": (
                        movie_details.get("overview", "")[:200] + "..."
                        if len(movie_details.get("overview", "")) > 200
                        else movie_details.get("overview", "")
                    ),
                    "rating": (
                        f"{movie_details.get('vote_average', 0):.1f}/10"
                        if movie_details.get("vote_average")
                        else ""
                    ),
                }
            else:
                # Fallback to basic search result
                return {
                    "error": False,
                    "title": movie.get("title", "Unknown"),
                    "year": (
                        movie.get("release_date", "")[:4]
                        if movie.get("release_date")
                        else ""
                    ),
                    "tmdb_url": f"https://www.themoviedb.org/movie/{movie_id}",
                    "overview": (
                        movie.get("overview", "")[:200] + "..."
                        if len(movie.get("overview", "")) > 200
                        else movie.get("overview", "")
                    ),
                    "rating": (
                        f"{movie.get('vote_average', 0):.1f}/10"
                        if movie.get("vote_average")
                        else ""
                    ),
                }

        except requests.exceptions.Timeout:
            return {"error": True, "message": "Movie search request timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": True, "message": f"Movie search request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in movie search: {e}")
            return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def format_movie_info(self, movie_data: Dict[str, str]) -> str:
        """
        Format movie information into an IRC message.

        Args:
            movie_data: Movie data dictionary

        Returns:
            Formatted message string
        """
        if movie_data.get("error"):
            return (
                f"🎬 Movie search error: {movie_data.get('message', 'Unknown error')}"
            )

        title = movie_data.get("title", "Unknown title")
        year = movie_data.get("year", "")
        rating = movie_data.get("rating", "")
        imdb_url = movie_data.get("imdb_url", "")
        tmdb_url = movie_data.get("tmdb_url", "")

        # Build the response
        parts = [f"🎬 {title}"]
        if year:
            parts.append(f"({year})")
        if rating:
            parts.append(f"- {rating}")
        if imdb_url:
            parts.append(f"- {imdb_url}")
        elif tmdb_url:
            parts.append(f"- {tmdb_url}")

        return " ".join(parts)


def create_imdb_service() -> MovieSearchService:
    """
    Factory function to create a movie search service instance.

    Returns:
        MovieSearchService instance
    """
    return MovieSearchService()
