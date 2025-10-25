import asyncio
import logging
import os
import re
from typing import Callable, Optional

from bs4 import BeautifulSoup
from playwright.async_api import Page, Playwright, async_playwright


class OtiedoteService:
    """Service for monitoring Otiedote.fi press releases using Playwright."""

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
        self.running = False
        self.playwright: Optional[Playwright] = None
        self.browser = None
        self._load_latest_release()

    async def start(self) -> None:
        """Start monitoring press releases in an asyncio event loop."""
        if self.running:
            return
        self.running = True
        asyncio.create_task(self._monitor_loop())
        logging.info("✅ Otiedote monitor started")

    async def stop(self) -> None:
        """Stop monitoring press releases."""
        self.running = False
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logging.debug(f"Browser shutdown exception (expected): {e}")
            self.browser = None
        if self.playwright:
            self.playwright = None
        logging.info("🛑 Otiedote monitor stopped")

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

    async def _setup_browser(self) -> Optional[Page]:
        """Setup Playwright browser with headless configuration."""
        for attempt in range(3):
            try:
                self.playwright = await async_playwright().start()
                # Use Firefox to avoid Chrome; can switch to 'webkit' if needed
                self.browser = await self.playwright.firefox.launch(headless=True)
                context = await self.browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
                )
                return await context.new_page()
            except Exception as e:
                logging.warning(f"Browser setup attempt {attempt + 1} failed: {e}")
                if self.browser:
                    await self.browser.close()
                if self.playwright:
                    await self.playwright.stop()
                await asyncio.sleep(2)
        logging.critical("Browser failed to start after multiple attempts")
        return None

    async def _monitor_loop(self) -> None:
        """Main monitoring loop running in asyncio."""
        while self.running:
            page = None
            try:
                page = await self._setup_browser()
                if not page:
                    logging.error("Browser not available, retrying later")
                    await asyncio.sleep(self.check_interval)
                    continue

                await self._check_for_new_releases(page)

            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
            finally:
                if page:
                    await page.close()
                if self.browser:
                    await self.browser.close()
                    self.browser = None
                if self.playwright:
                    await self.playwright.stop()
                    self.playwright = None

            await asyncio.sleep(self.check_interval)

    async def _check_for_new_releases(self, page: Page) -> None:
        """Check for new press releases."""
        try:
            await page.goto(self.BASE_URL, wait_until="networkidle")
            await page.wait_for_selector(
                'tbody tr td a[href*="/release_view/"]', timeout=10000
            )

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
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

            new_releases.sort()
            for release in new_releases:
                await self._process_release(page, release)

        except Exception as e:
            logging.error(f"Error checking for new releases: {e}")

    async def _process_release(self, page: Page, release_number: int) -> None:
        """Process a specific release by fetching its details."""
        try:
            url = self.RELEASE_URL_TEMPLATE.format(release_number)
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_selector("h1", timeout=10000)

            html = await page.content()
            release_soup = BeautifulSoup(html, "html.parser")

            title_tag = release_soup.find("h1")
            title = title_tag.text.strip() if title_tag else f"Release {release_number}"

            description: Optional[str] = None
            try:
                label_b = release_soup.find(
                    "b",
                    string=lambda s: isinstance(s, str)
                    and "tapahtuman kuvaus" in s.lower(),
                )
                if label_b:
                    label_container = label_b.find_parent("div")
                    content_container = (
                        label_container.find_next_sibling("div")
                        if label_container
                        else None
                    )
                    if content_container:
                        paragraphs = content_container.select("p")
                        texts = [p.get_text(strip=True) for p in paragraphs]
                        texts = [t for t in texts if t]
                        if texts:
                            description = re.sub(r"\s+", " ", " ".join(texts)).strip()
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

            self.callback(title, url, description)
            self.latest_release = release_number
            self._save_latest_release(release_number)
            logging.info(
                f"Processed new release {release_number}: {title}{' (with description)' if description else ''}"
            )

        except Exception as e:
            logging.error(f"Failed to process release {release_number}: {e}")

    def get_latest_release_info(self) -> dict:
        """Get information about the latest tracked release."""
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


async def main():
    def callback(title: str, url: str, description: Optional[str]) -> None:
        print(f"New release: {title}, URL: {url}, Description: {description or 'N/A'}")

    service = create_otiedote_service(callback)
    await service.start()
    try:
        await asyncio.sleep(3600)  # Run for an hour
    finally:
        await service.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
