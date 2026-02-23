import json
import logging
import random
import re
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_chrome_driver():
    """Set up Chrome WebDriver with proper configuration"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome WebDriver initialized successfully")

        # Bypass CookieBot consent
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                // Override CookieBot consent
                window.CookieBot = { consent: { necessary: true, preferences: false, statistics: false, marketing: false } };
                window.CookieConsent = { get: function() { return true; } };
                Object.defineProperty(document, 'cookie', {
                    set: function(c) {
                        // Allow setting consent cookie
                        if (c.includes('CookieConsent') || c.includes('CookieBot')) return;
                    },
                    get: function() { return 'CookieConsent=true'; }
                });
            """
            },
        )

        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {e}")
        raise


def click_show_more_button(driver, max_attempts=50):
    """Click 'Näytä lisää tuloksia' button to load more content"""
    for attempt in range(max_attempts):
        try:
            # Wait for the button to be clickable - match input element with value and class
            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//input[@value='Näytä lisää tuloksia' and @class='btn']",
                    )
                )
            )
            driver.execute_script("arguments[0].click();", button)
            logger.info(
                f"Clicked 'Näytä lisää tuloksia' button (attempt {attempt + 1})"
            )
            time.sleep(3)  # Wait for content to load
        except TimeoutException:
            logger.info("No 'Näytä lisää tuloksia' button found or not clickable")
            break
        except Exception as e:
            logger.warning(f"Error clicking 'Näytä lisää tuloksia' button: {e}")
            break


def click_letter_buttons(driver):
    """Click individual letter buttons (A-Z) in random order to reveal all E-codes"""
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    random.shuffle(letters)  # Randomize the order of letters

    logger.info(f"Clicking letter buttons in random order: {letters}")

    for letter in letters:
        try:
            # Look for button with the letter
            xpath = f"//button[contains(text(), '{letter}')]"
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            driver.execute_script("arguments[0].click();", button)
            logger.info(f"Clicked letter button: {letter}")
            time.sleep(2)  # Wait for content to load

            # Check if clicking the button revealed new content
            current_content = driver.page_source
            soup = BeautifulSoup(current_content, "html.parser")
            ecode_matches = re.findall(r"E\s*\d+", soup.get_text())
            logger.info(f"After clicking {letter}: Found {len(ecode_matches)} E-codes")

        except TimeoutException:
            logger.debug(f"Letter button {letter} not found or not clickable")
            continue
        except Exception as e:
            logger.warning(f"Error clicking letter button {letter}: {e}")
            continue


def click_ecode_buttons(driver):
    """Click individual E-code buttons to reveal detailed information"""
    logger.info("Clicking individual E-code buttons...")

    # Find all E-code buttons
    try:
        # Look for buttons that contain E-codes
        xpath = "//button[contains(text(), 'E') and contains(text(), ' ') and not(contains(text(), 'Näytä lisää'))]"
        ecode_buttons = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, xpath))
        )

        logger.info(f"Found {len(ecode_buttons)} E-code buttons")

        # Click each E-code button and extract detailed information
        for i, button in enumerate(ecode_buttons):
            try:
                # Get the button text to identify the E-code
                button_text = button.text.strip()
                if re.match(r"E\s*\d+", button_text):
                    driver.execute_script("arguments[0].click();", button)
                    logger.info(f"Clicked E-code button: {button_text}")
                    time.sleep(2)  # Wait for content to load

                    # Extract detailed information after clicking
                    current_page_source = driver.page_source
                    soup = BeautifulSoup(current_page_source, "html.parser")

                    # Look for the expanded content area that contains detailed information
                    # This might be in a different container after clicking
                    expanded_content = soup.find(
                        "div",
                        class_=re.compile(
                            r".*expanded.*|.*content.*|.*details.*", re.IGNORECASE
                        ),
                    )
                    if not expanded_content:
                        # Try to find any div that contains the E-code and detailed text
                        expanded_content = soup.find(
                            "div",
                            string=re.compile(r"Kuvaus:|ADI:|Valmistetaan|Käytetään"),
                        )

                    if expanded_content:
                        detailed_text = expanded_content.get_text()
                        logger.info(f"Extracted detailed content for {button_text}")
                    else:
                        # Fallback: get all text from the page
                        detailed_text = soup.get_text()
                        logger.info(f"Using full page content for {button_text}")

                    # Store the detailed information for this E-code
                    ecode_match = re.search(r"E\s*(\d+)", button_text)
                    if ecode_match:
                        ecode_number = ecode_match.group(1)
                        ecode_key = f"E{ecode_number}"

                        # Extract information from the detailed content using BeautifulSoup
                        adi_info = extract_adi_information(soup)  # Pass soup, not text
                        description = extract_description(soup)

                        logger.info(
                            f"Extracted for {ecode_key}: ADI={adi_info}, Description={description}"
                        )

                    # If we've clicked many buttons, take a short break to avoid overwhelming the page
                    if (i + 1) % 5 == 0:
                        time.sleep(3)

            except Exception as e:
                logger.warning(f"Error clicking E-code button: {e}")
                continue

    except TimeoutException:
        logger.info("No E-code buttons found or not clickable")
    except Exception as e:
        logger.warning(f"Error finding E-code buttons: {e}")


def extract_adi_information(soup_or_text):
    """Extract ADI information - handles BeautifulSoup objects or text strings"""
    # Check if we have a BeautifulSoup object (it has find_all method)
    if hasattr(soup_or_text, "find_all"):
        # It's a BeautifulSoup object - use HTML structure
        soup = soup_or_text
        # Find all dt elements that contain ADI info
        dt_elements = soup.find_all("dt")
        for dt in dt_elements:
            dt_text = dt.get_text()
            if (
                "ADI" in dt_text
                or "Hyvaeksyttaeva paivittaenen enimmaisaanti" in dt_text
            ):
                # Get the next sibling dd element
                dd = dt.find_next_sibling("dd")
                if dd:
                    adi_info = dd.get_text().strip()
                    # Clean up the ADI information
                    adi_info = re.sub(
                        r"\s*Siirry sivulle\s+E\d+\s*",
                        "",
                        adi_info,
                        flags=re.IGNORECASE,
                    )
                    adi_info = adi_info.strip()
                    return adi_info if adi_info else None
        return None
    else:
        # It's a text string - use regex patterns
        text = soup_or_text


def extract_description(soup_or_text):
    """Extract description (Kuvaus) - handles BeautifulSoup objects or text strings"""
    # Check if we have a BeautifulSoup object (it has find_all method)
    if hasattr(soup_or_text, "find_all"):
        # It's a BeautifulSoup object - use HTML structure
        soup = soup_or_text
        # Find dt element containing Kuvaus
        dt_elements = soup.find_all("dt")
        for dt in dt_elements:
            dt_text = dt.get_text()
            if "Kuvaus" in dt_text:
                # Get the next sibling dd element
                dd = dt.find_next_sibling("dd")
                if dd:
                    return dd.get_text().strip()
        return None
    else:
        # It's a text string - use regex
        text = soup_or_text


def parse_ecode_details(soup):
    """Parse detailed E-code information from the page"""
    ecode_data = {}

    # Find all E-code entries
    ecode_entries = soup.find_all(["div", "button"], class_=re.compile(r".*"))

    for entry in ecode_entries:
        entry_text = entry.get_text()

        # Look for E-code pattern
        ecode_match = re.search(r"E\s*(\d+)", entry_text)
        if ecode_match:
            ecode_number = ecode_match.group(1)
            ecode_key = f"E{ecode_number}"

            # Extract the full text content for this entry
            full_text = entry_text

            # Extract ADI information
            adi_info = extract_adi_information(full_text)

            # Extract additional information
            # additional_info not available
            additional_info = None

            # Extract description
            description = extract_description(full_text)

            # Store the information
            if ecode_key not in ecode_data:
                ecode_data[ecode_key] = {
                    "name": "",
                    "additional_info": additional_info,
                    "description": description,
                    "ADI": adi_info,
                }
            else:
                # Merge information if already exists
                if additional_info:
                    ecode_data[ecode_key]["additional_info"] = additional_info
                if description:
                    ecode_data[ecode_key]["description"] = description
                if adi_info:
                    # ADI is now a string, just assign it
                    ecode_data[ecode_key]["ADI"] = adi_info

    return ecode_data


def scrape_all_ecodes_adi():
    """Main function to scrape all E-codes and their ADI information"""
    driver = None
    try:
        # Set up WebDriver
        driver = setup_chrome_driver()

        # Navigate to the page
        url = "https://www.ruokavirasto.fi/elintarvikkeet/ohjeita-kuluttajille/e-kooditlisaaineet/e-koodit/"
        logger.info(f"Fetching data from: {url}")

        driver.get(url)

        # Wait for initial content to load
        time.sleep(5)

        # Click "Näytä lisää tuloksia" button multiple times
        logger.info("Clicking 'Näytä lisää tuloksia' button...")
        click_show_more_button(driver)

        # Click individual letter buttons
        logger.info("Clicking letter buttons A-Z...")
        click_letter_buttons(driver)

        # Click individual E-code buttons to reveal detailed information
        logger.info("Clicking E-code buttons to reveal detailed information...")
        click_ecode_buttons(driver)

        # Get the final page source after all interactions
        final_page_source = driver.page_source
        soup = BeautifulSoup(final_page_source, "html.parser")

        # Extract E-code information
        logger.info("Extracting E-code information...")
        scraped_data = parse_ecode_details(soup)

        # Get all E-codes found
        all_ecodes = re.findall(r"E\s*\d+", soup.get_text())
        unique_ecodes = list(set(all_ecodes))

        logger.info(f"Total unique E-codes found: {len(unique_ecodes)}")
        logger.info(f"Sample E-codes: {unique_ecodes[:10]}")

        # Check for specific E-codes
        if "E586" in scraped_data:
            logger.info(f"E586 found with ADI: {scraped_data['E586']['ADI']}")
        if "E334" in scraped_data:
            logger.info(f"E334 found with ADI: {scraped_data['E334']['ADI']}")

        return scraped_data, unique_ecodes

    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        return {}, []

    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")


def load_existing_ecodes():
    """Load existing E-codes data from data/ecodes.json"""
    try:
        # Get the project root directory (two levels up from src/debug)
        import os

        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        ecodes_path = os.path.join(project_root, "data", "ecodes.json")

        with open(ecodes_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Existing E-codes data loaded successfully")
        return data
    except FileNotFoundError:
        logger.warning("data/ecodes.json not found, creating new structure")
        return {"symbol_definitions": {}, "indicator_definitions": {}, "ecodes": {}}
    except Exception as e:
        logger.error(f"Error loading existing E-codes data: {e}")
        return {"symbol_definitions": {}, "indicator_definitions": {}, "ecodes": {}}


def merge_ecode_data(existing_data, scraped_data):
    """Merge scraped data with existing E-codes data"""
    updated_count = 0
    new_count = 0

    for ecode_key, scraped_info in scraped_data.items():
        if ecode_key in existing_data["ecodes"]:
            # Update existing E-code
            existing_ecode = existing_data["ecodes"][ecode_key]

            # Update ADI information (now a string, not a list)
            if scraped_info.get("ADI"):
                # The scraped ADI is now a clean string
                existing_ecode["ADI"] = scraped_info["ADI"]
                updated_count += 1
                logger.info(f"Updated ADI for {ecode_key}: {scraped_info['ADI']}")

            # Update additional information
            if scraped_info.get("additional_info"):
                existing_ecode["additional_info"] = scraped_info["additional_info"]
                logger.info(f"Updated additional info for {ecode_key}")

            # Update description
            if scraped_info.get("description"):
                existing_ecode["description"] = scraped_info["description"]
                logger.info(
                    f"Updated description for {ecode_key}: {scraped_info['description']}"
                )
        else:
            # Add new E-code (if we have complete information)
            if (
                scraped_info["ADI"]
                or scraped_info["additional_info"]
                or scraped_info["description"]
            ):
                # ADI is now a string, not a list
                new_adi = scraped_info.get("ADI")

                # Create minimal E-code entry
                new_ecode = {
                    "categories": [],
                    "name": scraped_info.get("name", ""),
                    "indicators": [],
                    "additional_info": scraped_info.get("additional_info"),
                    "description": scraped_info.get("description"),
                    "ADI": new_adi,
                }
                existing_data["ecodes"][ecode_key] = new_ecode
                new_count += 1
                logger.info(f"Added new E-code: {ecode_key}")

    logger.info(f"Merged data: {updated_count} updated, {new_count} new")
    return updated_count, new_count


def save_ecodes_data(data):
    """Save updated E-codes data to data/ecodes.json"""
    try:
        # Get the project root directory (two levels up from src/debug)
        import os

        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        ecodes_path = os.path.join(project_root, "data", "ecodes.json")

        with open(ecodes_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"E-codes data saved successfully to {ecodes_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving E-codes data: {e}")
        return False


def main():
    """Main execution function"""
    logger.info("Starting comprehensive E-codes ADI scraping...")

    # Load existing data
    existing_data = load_existing_ecodes()

    # Scrape new data
    scraped_data, unique_ecodes = scrape_all_ecodes_adi()

    if not scraped_data:
        logger.error("No E-code data was scraped. Exiting.")
        return False

    # Merge data
    updated_count, new_count = merge_ecode_data(existing_data, scraped_data)

    # Save updated data
    success = save_ecodes_data(existing_data)

    # Print summary
    logger.info("=" * 60)
    logger.info("SCRAPING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total unique E-codes found: {len(unique_ecodes)}")
    logger.info(f"E-codes with ADI information: {len(scraped_data)}")
    logger.info(f"Existing E-codes updated: {updated_count}")
    logger.info(f"New E-codes added: {new_count}")

    # Check specific E-codes
    if "E586" in existing_data["ecodes"]:
        logger.info(f"E586 ADI: {existing_data['ecodes']['E586']['ADI']}")
    if "E334" in existing_data["ecodes"]:
        logger.info(f"E334 ADI: {existing_data['ecodes']['E334']['ADI']}")

    logger.info("=" * 60)

    return success


if __name__ == "__main__":
    success = main()
    if success:
        logger.info("E-codes ADI scraping completed successfully!")
    else:
        logger.error("E-codes ADI scraping failed!")
