import os
import re
import time
import threading
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup


class OtiedoteMonitor:
    BASE_URL = "https://otiedote.fi/pohjois-karjalan-pelastuslaitos"
    RELEASE_URL_TEMPLATE = "https://otiedote.fi/release_view/{}"
    CHECK_INTERVAL = 5 * 60  # 5 minutes
    STATE_FILE = "latest_otiedote.txt"

    def __init__(self, callback, check_interval=None):
        """
        :param callback: function to call with (title, url) when a new release is found
        :param check_interval: optional override for check interval in seconds
        """
        self.callback = callback
        self.check_interval = check_interval or self.CHECK_INTERVAL
        self.latest_release = 2039  # Default fallback 19.5.2025
        self.driver = None
        self.thread = None
        self.running = False

        self._load_latest_release()
        self._setup_driver()

    def _setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        service = Service(log_path=os.devnull)
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print("Virhe WebDriverin käynnistyksessä:", e)

    def _load_latest_release(self):
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, "r") as f:
                    self.latest_release = int(f.read().strip())
            except Exception as e:
                logging.warning(f"Failed to read state file: {e}")

    def _save_latest_release(self, release):
        try:
            with open(self.STATE_FILE, "w") as f:
                f.write(str(release))
        except Exception as e:
            logging.warning(f"Failed to save state: {e}")

    def _fetch_announcements(self):
        while self.running:
            try:
                self.driver.get(self.BASE_URL)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "tbody tr td a[href*='/release_view/']")
                    )
                )
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

                if new_releases:
                    new_releases.sort()
                    for release in new_releases:
                        url = self.RELEASE_URL_TEMPLATE.format(release)
                        try:
                            self.driver.get(url)
                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.TAG_NAME, "h1"))
                            )
                            release_soup = BeautifulSoup(
                                self.driver.page_source, "html.parser"
                            )
                            title_tag = release_soup.find("h1")
                            title = (
                                title_tag.text.strip() if title_tag else ""
                            )  # No title
                            description_tag = release_soup.find(
                                "#releaseCommentsWrapper > ul > li > p"
                            )
                            description = (
                                description_tag.text.strip() if description_tag else ""
                            )  # No description
                            print("Description: " + description)
                            title += description
                            self.callback(title, url)
                            self.latest_release = release
                            self._save_latest_release(release)
                        except Exception as e:
                            logging.error(f"Failed to process release {release}: {e}")
                else:
                    logging.info("No new releases found.")

            except Exception as e:
                logging.error(f"Error fetching announcements: {e}")

            time.sleep(self.check_interval)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._fetch_announcements, daemon=True)
        self.thread.start()
        logging.info("Otiedote monitor started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.driver:
            self.driver.quit()
        logging.info("Otiedote monitor stopped.")
