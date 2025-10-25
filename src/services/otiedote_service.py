"""
Otiedote Monitor Service Module

Monitors Pohjois-Karjalan pelastuslaitos (North Karelia Rescue Service)
press releases from otiedote.fi and provides notifications for new releases.
"""

import logging
import os
import re
import threading
import time
from typing import Callable, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class OtiedoteService:
    """Service for monitoring Otiedote.fi press releases."""

    BASE_URL = "https://otiedote.fi/pohjois-karjalan-pelastuslaitos"
    RELEASE_URL_TEMPLATE = "https://otiedote.fi/release_view/{}"
    DEFAULT_CHECK_INTERVAL = 15 * 60  # 15 minutes
    DEFAULT_STATE_FILE = "latest_otiedote.txt"

    def __init__(
        self,
        callback: Callable[[str, str, Optional[str]], None],
        state_file: str = DEFAULT_STATE_FILE,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
    ):
        """
        Initialize Otiedote monitoring service.

        Args:
            callback: Function to call with (title, url, description) when new release is found
            state_file: File to store latest release number
            check_interval: Check interval in seconds
        """
        self.callback = callback
        self.state_file = state_file
        self.check_interval = check_interval
        self.latest_release = 2597  # Default fallback 11.9.2025
        self.driver: Optional[webdriver.Chrome] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

        self._load_latest_release()

    def start(self) -> None:
        """Start monitoring press releases in background thread."""
        if self.thread and self.thread.is_alive():
            return

        self.running = True
        self._setup_driver()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logging.info("✅ Otiedote monitor started")

    def stop(self) -> None:
        """Stop monitoring press releases."""
        self.running = False
        if self.thread:
            # Join with longer timeout to allow graceful shutdown
            self.thread.join(timeout=30.0)
            if self.thread.is_alive():
                logging.warning(
                    "⚠️ Otiedote monitor thread did not stop cleanly within 30s timeout"
                )
        if self.driver:
            # Suppress urllib3 connectionpool warnings while shutting down the driver
            import logging as _pylogging

            _urllib3_logger = _pylogging.getLogger("urllib3.connectionpool")
            _prev_level = _urllib3_logger.level
            try:
                _urllib3_logger.setLevel(_pylogging.CRITICAL)
                try:
                    # First try to close gracefully
                    self.driver.close()
                except Exception:
                    # Ignore close errors during shutdown
                    pass
                try:
                    self.driver.quit()
                except Exception:
                    # Ignore quit errors during shutdown
                    pass
            except Exception as e:
                logging.debug(f"WebDriver shutdown exception (expected): {e}")
            finally:
                try:
                    _urllib3_logger.setLevel(_prev_level)
                except Exception:
                    pass
                self.driver = None
        logging.info("🛑 Otiedote monitor stopped")

    def _setup_driver(self) -> None:
        """Setup Chrome WebDriver with headless configuration."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")

        service = Service(log_path=os.devnull)

        for attempt in range(3):
            try:
                # Prefer to disable keep_alive to avoid HTTP retries on shutdown
                try:
                    self.driver = webdriver.Chrome(
                        service=service, options=chrome_options, keep_alive=False
                    )
                except TypeError:
                    # Older selenium versions don't support keep_alive kwarg
                    self.driver = webdriver.Chrome(
                        service=service, options=chrome_options
                    )
                return
            except Exception as e:
                logging.warning(f"WebDriver setup attempt {attempt + 1} failed: {e}")
                time.sleep(2)

        logging.critical("WebDriver failed to start after multiple attempts")
        self.driver = None

    def _load_latest_release(self) -> None:
        """Load latest release number from state file."""
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.latest_release = int(f.read().strip())
        except (ValueError, IOError) as e:
            logging.warning(f"Failed to read state file: {e}")

    def _save_latest_release(self, release: int) -> None:
        """Save latest release number to state file."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                f.write(str(release))
        except IOError as e:
            logging.warning(f"Failed to save state: {e}")

    def _interruptible_sleep(self, duration: float) -> None:
        """Sleep for the specified duration but wake up periodically to check for shutdown."""
        sleep_chunk = 1.0  # Check every second
        elapsed = 0.0
        while elapsed < duration and self.running:
            chunk_time = min(sleep_chunk, duration - elapsed)
            time.sleep(chunk_time)
            elapsed += chunk_time

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self.running:
            try:
                if not self.driver:
                    self._setup_driver()

                if not self.driver:
                    logging.error("WebDriver not available, retrying later")
                    # Sleep in smaller chunks to be more responsive to shutdown
                    self._interruptible_sleep(self.check_interval)
                    continue

                self._check_for_new_releases()

            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")

            # Sleep in smaller chunks to be more responsive to shutdown
            self._interruptible_sleep(self.check_interval)

    def _check_for_new_releases(self) -> None:
        """Check for new press releases."""
        try:
            # Load the main page
            self.driver.get(self.BASE_URL)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "tbody tr td a[href*='/release_view/']")
                )
            )

            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            release_links = soup.select('tbody tr td a[href*="/release_view/"]')

            new_releases = []
            for link in release_links:
                href = link.get("href")
                match = re.search(r"/release_view/(\d+)", href)
                if match:
                    release_number = int(match.group(1))
                    if release_number > self.latest_release:
                        new_releases.append(release_number)

            if not new_releases:
                logging.info("No new releases found")
                return

            # Process new releases in order
            new_releases.sort()
            for release in new_releases:
                self._process_release(release)

        except Exception as e:
            logging.error(f"Error checking for new releases: {e}")

    def _process_release(self, release_number: int) -> None:
        """
        Process a specific release by fetching its details.

        Args:
            release_number: Release number to process
        """
        try:
            url = self.RELEASE_URL_TEMPLATE.format(release_number)
            self.driver.get(url)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )

            # Parse release page
            release_soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Extract title
            title_tag = release_soup.find("h1")
            title = title_tag.text.strip() if title_tag else f"Release {release_number}"

            # Extract description by locating the "Tapahtuman kuvaus:" label and collecting following paragraphs
            description: Optional[str] = None
            try:
                # Find the bold label
                label_b = release_soup.find(
                    "b",
                    string=lambda s: isinstance(s, str)
                    and "tapahtuman kuvaus" in s.lower(),
                )
                if label_b:
                    # Typically inside col-lg-2; the content is in the next sibling col-lg-10
                    label_container = label_b.find_parent("div")
                    content_container = (
                        label_container.find_next_sibling("div")
                        if label_container
                        else None
                    )
                    if content_container:
                        # Gather all paragraph texts under the content container
                        paragraphs = content_container.select("p")
                        texts = [p.get_text(strip=True) for p in paragraphs]
                        texts = [t for t in texts if t]
                        if texts:
                            description = re.sub(r"\s+", " ", " ".join(texts)).strip()
                # Fallback: try common wrapper id if present
                if not description:
                    fallback_tag = release_soup.select_one("#releaseCommentsWrapper p")
                    if fallback_tag and fallback_tag.get_text(strip=True):
                        description = re.sub(
                            r"\s+", " ", fallback_tag.get_text(strip=True)
                        ).strip()
            except Exception as parse_err:
                logging.debug(
                    f"Description parsing error for release {release_number}: {parse_err}"
                )

            # Notify callback with separate description
            self.callback(title, url, description)

            # Update state
            self.latest_release = release_number
            self._save_latest_release(release_number)

            logging.info(
                f"Processed new release {release_number}: {title}{' (with description)' if description else ''}"
            )

        except Exception as e:
            logging.error(f"Failed to process release {release_number}: {e}")

    def get_latest_release_info(self) -> dict:
        """
        Get information about the latest tracked release.

        Returns:
            Dictionary with latest release information
        """
        return {
            "latest_release": self.latest_release,
            "state_file": self.state_file,
            "running": self.running,
        }


def create_otiedote_service(
    callback: Callable[[str, str, Optional[str]], None],
    state_file: str = OtiedoteService.DEFAULT_STATE_FILE,
    check_interval: int = OtiedoteService.DEFAULT_CHECK_INTERVAL,
) -> OtiedoteService:
    """
    Factory function to create an Otiedote service instance.

    Args:
        callback: Function to call with (title, url, description) when new release is found
        state_file: File to store latest release number
        check_interval: Check interval in seconds

    Returns:
        OtiedoteService instance
    """
    return OtiedoteService(callback, state_file, check_interval)
