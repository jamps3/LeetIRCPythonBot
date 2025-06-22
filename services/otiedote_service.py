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
    DEFAULT_CHECK_INTERVAL = 5 * 60  # 5 minutes
    DEFAULT_STATE_FILE = "latest_otiedote.txt"

    def __init__(
        self,
        callback: Callable[[str, str], None],
        state_file: str = DEFAULT_STATE_FILE,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
    ):
        """
        Initialize Otiedote monitoring service.

        Args:
            callback: Function to call with (title, url) when new release is found
            state_file: File to store latest release number
            check_interval: Check interval in seconds
        """
        self.callback = callback
        self.state_file = state_file
        self.check_interval = check_interval
        self.latest_release = 2039  # Default fallback
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
            # Join with timeout to prevent hanging during shutdown
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logging.warning("⚠️ Otiedote monitor thread did not stop cleanly within timeout")
        if self.driver:
            try:
                self.driver.quit()
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
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
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

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self.running:
            try:
                if not self.driver:
                    self._setup_driver()
                
                if not self.driver:
                    logging.error("WebDriver not available, retrying later")
                    time.sleep(self.check_interval)
                    continue

                self._check_for_new_releases()

            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")

            time.sleep(self.check_interval)

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

            # Try to extract description (this selector might need adjustment)
            description_tag = release_soup.select_one("#releaseCommentsWrapper > ul > li > p")
            if description_tag:
                description = description_tag.text.strip()
                if description:
                    title = f"{title} - {description}"

            # Notify callback
            self.callback(title, url)
            
            # Update state
            self.latest_release = release_number
            self._save_latest_release(release_number)
            
            logging.info(f"Processed new release {release_number}: {title}")

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
    callback: Callable[[str, str], None],
    state_file: str = OtiedoteService.DEFAULT_STATE_FILE,
    check_interval: int = OtiedoteService.DEFAULT_CHECK_INTERVAL,
) -> OtiedoteService:
    """
    Factory function to create an Otiedote service instance.

    Args:
        callback: Function to call with (title, url) when new release is found
        state_file: File to store latest release number
        check_interval: Check interval in seconds

    Returns:
        OtiedoteService instance
    """
    return OtiedoteService(callback, state_file, check_interval)
