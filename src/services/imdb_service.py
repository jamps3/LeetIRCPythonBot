"""
IMDb Service Module

Provides movie search functionality using IMDb website scraping.
"""

import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from logger import get_logger

logger = get_logger("IMDbService")


class IMDbService:
    """Service for searching movies on IMDb."""

    def __init__(self):
        """Initialize IMDb service."""
        self.base_url = "https://www.imdb.com"
        self.search_url = f"{self.base_url}/search/title/"

    def search_movie(self, query: str) -> Dict[str, str]:
        """
        Search for a movie on IMDb.

        Args:
            query: Movie title to search for

        Returns:
            Dictionary containing movie info or error details
        """
        try:
            # Clean and prepare the query
            query = query.strip()
            if not query:
                return {"error": True, "message": "Empty search query"}

            # Prepare search parameters - use minimal parameters to avoid filtering
            params = {
                "title": query,
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            # Make the search request
            response = requests.get(
                self.search_url, params=params, headers=headers, timeout=10
            )

            if response.status_code != 200:
                return {
                    "error": True,
                    "message": f"IMDb returned status code {response.status_code}",
                }

            # Parse the results
            return self._parse_search_results(response.text, query)

        except requests.exceptions.Timeout:
            return {"error": True, "message": "IMDb search request timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": True, "message": f"IMDb search request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in IMDb search: {e}")
            return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def _parse_search_results(self, html: str, query: str) -> Dict[str, str]:
        """
        Parse IMDb search results HTML.

        Args:
            html: Raw HTML from search results page
            query: Original search query

        Returns:
            Dictionary containing movie info or error details
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Strategy 1: Use regex to find IMDb title links (most reliable)
            logger.debug("Trying Strategy 1: Regex-based parsing")
            title_links = re.findall(
                r'href="(/title/tt\d+/?[^"]*)"[^>]*>([^<]+)</a>', html, re.IGNORECASE
            )

            if title_links:
                logger.debug(f"Found {len(title_links)} title links via regex")
                for link, title_text in title_links:
                    title = self._clean_title_text(title_text)

                    if len(title) < 3 or title.lower().startswith(
                        ("imdb", "home", "search", "advanced")
                    ):
                        continue

                    imdb_id_match = re.search(r"/title/(tt\d+)/", link)
                    if imdb_id_match:
                        imdb_id = imdb_id_match.group(1)

                        # For queries that include a year, try to find the best match
                        if re.search(r"\b(19|20)\d{2}\b", query):
                            # For year queries, fetch the title and check if it contains the year
                            actual_title = self._fetch_movie_title(imdb_id)
                            if actual_title and re.search(r"\b(19|20)\d{2}\b", query):
                                query_year_match = re.search(r"\b(19|20)\d{2}\b", query)
                                if query_year_match:
                                    query_year = query_year_match.group(0)
                                    if query_year in actual_title:
                                        logger.debug(
                                            f"Found year-matched result: '{actual_title}' for query year {query_year}"
                                        )
                                        return {
                                            "error": False,
                                            "title": actual_title,
                                            "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                                        }
                            # Continue looking for year match
                            continue
                        else:
                            # No year in query, return first valid result
                            actual_title = self._fetch_movie_title(imdb_id)
                            if actual_title:
                                logger.debug(f"Using fetched title: '{actual_title}'")
                                return {
                                    "error": False,
                                    "title": actual_title,
                                    "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                                }
                            else:
                                # Fallback to parsed title if fetching fails
                                return {
                                    "error": False,
                                    "title": title,
                                    "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                                }

            # Strategy 2: Fallback to complex BeautifulSoup parsing
            logger.debug("Trying Strategy 2: BeautifulSoup parsing")
            results = (
                soup.select('div[data-testid="search-result"]')
                or soup.select(".ipc-metadata-list-summary-item")
                or soup.select(".find-result-item")
                or soup.select(".lister-item")
            )

            logger.debug(f"Strategy 2: Found {len(results)} results")

            if results:
                for result in results:
                    # Extract title - prefer the official search result title link
                    title_element = result.select_one(
                        'a[data-testid="search-result__title-link"]'
                    ) or result.select_one('a[href*="/title/tt"]')

                    if not title_element:
                        continue

                    href = title_element.get("href")
                    title_text = title_element.get_text(strip=True)

                    # Skip if href doesn't contain a valid IMDb ID
                    if not re.search(r"/title/tt\d+", href):
                        continue

                    # Extract IMDb ID from the link
                    imdb_id_match = re.search(r"/title/(tt\d+)/", href)
                    if imdb_id_match:
                        imdb_id = imdb_id_match.group(1)

                        # Always fetch the actual title from the movie page for accuracy
                        actual_title = self._fetch_movie_title(imdb_id)
                        if actual_title:
                            return {
                                "error": False,
                                "title": actual_title,
                                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                            }

            # Strategy 3: Check if we got redirected to a direct title page
            title_element = (
                soup.find("h1", {"data-testid": "hero__pageTitle"})
                or soup.find("h1", class_=re.compile(r"hero__pageTitle"))
                or soup.find("title")
            )

            if title_element:
                title_text = title_element.get_text(strip=True)
                imdb_id_match = re.search(r"/title/(tt\d+)/", html)
                if imdb_id_match and title_text and len(title_text) > 3:
                    return {
                        "error": False,
                        "title": title_text,
                        "imdb_url": f"https://www.imdb.com/title/{imdb_id_match.group(1)}/",
                    }

            # Check for "no results" indicators
            if "no results" in html.lower() or "did not match any" in html.lower():
                return {"error": True, "message": f"No movies found for '{query}'"}

            return {
                "error": True,
                "message": f"Could not parse IMDb search results for '{query}'",
            }

        except Exception as e:
            logger.error(f"Error parsing IMDb HTML: {e}")
            return {"error": True, "message": f"Error parsing search results: {str(e)}"}

    def _fetch_movie_title(self, imdb_id: str) -> Optional[str]:
        """
        Fetch the actual movie title from IMDb movie page.

        Args:
            imdb_id: IMDb ID (e.g., 'tt0133093')

        Returns:
            Movie title or None if fetch failed
        """
        try:
            movie_url = f"https://www.imdb.com/title/{imdb_id}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }

            response = requests.get(movie_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.content, "html.parser")

            # Try multiple selectors for the movie title
            title_element = (
                soup.find("h1", {"data-testid": "hero__pageTitle"})
                or soup.find("h1", class_=re.compile(r"hero__primary-text"))
                or soup.find("title")
            )

            if title_element:
                title_text = title_element.get_text(strip=True)

                # Clean up the title - remove " - IMDb" suffix if present
                title_text = re.sub(r"\s*-\s*IMDb\s*$", "", title_text)

                # Keep the year in parentheses (don't remove it)
                return title_text.strip()

        except Exception as e:
            logger.error(f"Error fetching movie title for {imdb_id}: {e}")

        return None

    def _clean_title_text(self, title_text: str) -> str:
        """
        Clean up title text by removing numbering and extra formatting.

        Args:
            title_text: Raw title text from HTML

        Returns:
            Cleaned title text
        """
        # Remove numbering prefixes like "1. ", "2. ", etc.
        title = re.sub(r"^\d+\.\s*", "", title_text.strip())

        # Remove any remaining HTML entities or extra whitespace
        title = re.sub(r"\s+", " ", title).strip()

        return title

    def format_movie_info(self, movie_data: Dict[str, str]) -> str:
        """
        Format movie information into an IRC message.

        Args:
            movie_data: Movie data dictionary

        Returns:
            Formatted message string
        """
        if movie_data.get("error"):
            return f"🎬 IMDb error: {movie_data.get('message', 'Unknown error')}"

        title = movie_data.get("title", "Unknown title")
        imdb_url = movie_data.get("imdb_url", "")

        return f"🎬 {title} - {imdb_url}"


def create_imdb_service() -> IMDbService:
    """
    Factory function to create an IMDb service instance.

    Returns:
        IMDbService instance
    """
    return IMDbService()
