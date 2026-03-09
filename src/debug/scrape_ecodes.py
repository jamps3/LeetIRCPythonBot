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
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {e}")
        raise


def click_show_more_button(driver, max_attempts=3):
    """Click 'Näytä lisää tuloksia' button to load more content"""
    for attempt in range(max_attempts):
        try:
            # Wait for the button to be clickable
            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Näytä lisää tuloksia')]")
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

                        # Extract information from the detailed content
                        adi_info = extract_adi_information(detailed_text)
                        description = extract_description(detailed_text)

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


def extract_adi_information(text):
    """Extract ADI information from text content"""
    adi_info = []

    # Pattern for ADI information
    adi_patterns = [
        r"Hyväksyttävä päivittäinen enimmäissaanti \(ADI\):\s*([^.\n]+)",
        r"ADI:\s*([^.\n]+)",
        r"Ei ole määritelty",
        r"\d+\s*mg/kg/vrk",
        r"\d+\s*mg/\w+",
        r"E\d+-E\d+\s*ja\s*E\d+\s*yhteismäärälle\s*\d+\s*mg/kg/vrk",
    ]

    for pattern in adi_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        adi_info.extend(matches)

    # Clean up the ADI information
    cleaned_adi = []
    seen = set()

    for item in adi_info:
        # Remove "Siirry sivulle E..." text
        cleaned_item = re.sub(
            r"\s*Siirry sivulle\s+E\d+\s*", "", item, flags=re.IGNORECASE
        )
        # Remove extra whitespace
        cleaned_item = cleaned_item.strip()

        # Only add non-empty items and avoid duplicates
        if cleaned_item and cleaned_item not in seen:
            cleaned_adi.append(cleaned_item)
            seen.add(cleaned_item)

    return cleaned_adi


def extract_additional_info(text):
    """Extract additional information from E-code descriptions"""
    additional_info = []

    # Look for usage descriptions
    usage_patterns = [
        r"Käytetään\s+[^.\n]+",
        r"Valmistetaan\s+[^.\n]+",
        r"Esiintyy\s+[^.\n]+",
        r"Saa käyttää\s+[^.\n]+",
        r"Enimmäismäärärajoituksia",
        r"Ei enimmäismäärärajoituksia",
    ]

    for pattern in usage_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        additional_info.extend(matches)

    return additional_info if additional_info else None


def extract_description(text):
    """Extract description (Kuvaus) from E-code descriptions"""
    description = []

    # Look for description patterns
    description_patterns = [
        r"Kuvaus:\s*([^.\n]+)",
    ]

    for pattern in description_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        description.extend(matches)

    return description if description else None


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
            additional_info = extract_additional_info(full_text)

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
                    ecode_data[ecode_key]["ADI"].extend(adi_info)

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

            # Update ADI information with cleaning
            if scraped_info["ADI"]:
                # Clean the scraped ADI information
                cleaned_adi = []
                seen = set()

                for item in scraped_info["ADI"]:
                    # Remove "Siirry sivulle E..." text
                    cleaned_item = re.sub(
                        r"\s*Siirry sivulle\s+E\d+\s*", "", item, flags=re.IGNORECASE
                    )
                    # Remove extra whitespace
                    cleaned_item = cleaned_item.strip()

                    # Only add non-empty items and avoid duplicates
                    if cleaned_item and cleaned_item not in seen:
                        cleaned_adi.append(cleaned_item)
                        seen.add(cleaned_item)

                existing_ecode["ADI"] = cleaned_adi
                updated_count += 1
                logger.info(f"Updated ADI for {ecode_key}: {cleaned_adi}")

            # Update additional information
            if scraped_info["additional_info"]:
                existing_ecode["additional_info"] = scraped_info["additional_info"]
                logger.info(f"Updated additional info for {ecode_key}")

            # Update description
            if scraped_info["description"]:
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
                # Clean the scraped ADI information
                cleaned_adi = []
                if scraped_info["ADI"]:
                    seen = set()
                    for item in scraped_info["ADI"]:
                        # Remove "Siirry sivulle E..." text
                        cleaned_item = re.sub(
                            r"\s*Siirry sivulle\s+E\d+\s*",
                            "",
                            item,
                            flags=re.IGNORECASE,
                        )
                        # Remove extra whitespace
                        cleaned_item = cleaned_item.strip()

                        # Only add non-empty items and avoid duplicates
                        if cleaned_item and cleaned_item not in seen:
                            cleaned_adi.append(cleaned_item)
                            seen.add(cleaned_item)

                # Create minimal E-code entry
                new_ecode = {
                    "categories": [],
                    "name": scraped_info.get("name", ""),
                    "indicators": [],
                    "additional_info": scraped_info["additional_info"],
                    "description": scraped_info["description"],
                    "ADI": cleaned_adi,
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
