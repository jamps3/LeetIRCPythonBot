"""
Alko Service Module

Provides Alko (Finnish alcohol monopoly) price and product information.
Downloads and parses the Alko price list Excel file.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

import logger

logger = logger.get_logger("AlkoService")


class AlkoService:
    """Service for fetching Alko product information from Excel price list."""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize Alko service.

        Args:
            data_dir: Directory where data files are stored
        """
        self.data_dir = Path(data_dir)
        self.excel_url = (
            "https://www.alko.fi/INTERSHOP/static/WFS/Alko-OnlineShop-Site/-/"
            "Alko-OnlineShop/fi_FI/Alkon%20Hinnasto%20Tekstitiedostona/"
            "alkon-hinnasto-tekstitiedostona.xlsx"
        )
        self.local_excel_path = self.data_dir / "alkon-hinnasto-tekstitiedostona.xlsx"
        self.cache_file = self.data_dir / "alko_cache.json"
        self.products_cache: Optional[List[Dict[str, Any]]] = None
        self.last_update_check = None

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Load cached data if available
        self._load_cache()

        # Force re-parse of Excel file to update calculations
        if self.local_excel_path.exists():
            logger.info("Re-parsing Excel file to update alcohol calculations...")
            products = self._parse_excel_file()
            if products:
                self.products_cache = products
                self._save_cache()
                logger.info(
                    f"Successfully re-parsed {len(products)} products from Excel file"
                )
            else:
                logger.warning("Failed to re-parse existing Excel file")
        else:
            # Auto-update data if needed (no cache or empty cache)
            if not self.products_cache:
                # First try to parse existing Excel file if it exists
                if self.local_excel_path.exists():
                    logger.info(
                        "No cache available, attempting to parse existing Excel file..."
                    )
                    products = self._parse_excel_file()
                    if products:
                        self.products_cache = products
                        self._save_cache()
                        logger.info(
                            f"Successfully loaded {len(products)} products from existing Excel file"
                        )
                    else:
                        logger.warning("Failed to parse existing Excel file")

                # If still no data, try downloading
                if not self.products_cache:
                    logger.info("No Alko data available, attempting to download...")
                    success = self.update_data(force=True)
                    if not success:
                        logger.warning(
                            "Failed to download Alko data. The !alko command will not work until data is available."
                        )
                        logger.warning(
                            "You can manually download the Excel file from Alko and place it at:"
                        )
                        logger.warning(f"  {self.local_excel_path}")
                        logger.warning(
                            "Or run the bot with cached data if you have it."
                        )

    def _load_cache(self):
        """Load cached product data if available."""
        try:
            if self.cache_file.exists():
                import json

                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    self.products_cache = cache_data.get("products", [])
                    logger.info(
                        f"Loaded {len(self.products_cache)} products from cache"
                    )
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self.products_cache = None

    def _save_cache(self):
        """Save product data to cache."""
        try:
            import json

            cache_data = {
                "products": self.products_cache,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.products_cache)} products to cache")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _get_remote_file_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the remote Excel file."""
        try:
            # Get headers only to check file size and last modified
            response = requests.head(self.excel_url, timeout=30)
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            last_modified = response.headers.get("Last-Modified")

            return {
                "content_length": int(content_length) if content_length else None,
                "last_modified": last_modified,
                "url": self.excel_url,
            }
        except Exception as e:
            logger.error(f"Failed to get remote file info: {e}")
            return None

    def _should_download_file(self) -> bool:
        """Check if the Excel file should be downloaded."""
        if not self.local_excel_path.exists():
            logger.info("Local Excel file does not exist, downloading")
            return True

        # Check remote file info
        remote_info = self._get_remote_file_info()
        if not remote_info:
            logger.warning("Could not get remote file info, skipping download")
            return False

        # Compare file sizes
        try:
            local_size = self.local_excel_path.stat().st_size
            remote_size = remote_info.get("content_length")

            if remote_size and local_size != remote_size:
                logger.info(
                    f"File size changed: local {local_size} vs remote {remote_size}, downloading"
                )
                return True

        except Exception as e:
            logger.warning(f"Could not compare file sizes: {e}")

        # Check if cache is empty or old
        if not self.products_cache:
            logger.info("No cached products, downloading")
            return True

        # Don't download more than once per hour unless forced
        if self.last_update_check:
            time_since_check = (datetime.now() - self.last_update_check).total_seconds()
            if time_since_check < 3600:  # 1 hour
                return False

        self.last_update_check = datetime.now()
        return False

    def _download_excel_file(self) -> bool:
        """Download the Excel file from Alko."""
        try:
            logger.info("Downloading Excel file from Alko...")

            # Add headers to appear more like a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel, */*",
                "Accept-Language": "en-US,en;q=0.9,fi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            response = requests.get(
                self.excel_url, timeout=60, stream=True, headers=headers
            )
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "html" in content_type:
                # Check if this is bot protection (Incapsula)
                content_start = (
                    response.content[:500].decode("utf-8", errors="ignore").lower()
                )
                if "incapsula" in content_start or "challenge" in content_start:
                    logger.warning(
                        "Alko website returned bot protection page instead of Excel file"
                    )
                    logger.warning(
                        "The website may be blocking automated downloads. Please download manually from:"
                    )
                    logger.warning(f"  {self.excel_url}")
                    logger.warning(
                        "And place it as: data/alkon-hinnasto-tekstitiedostona.xlsx"
                    )
                    return False

            # Check content length - Excel files should be reasonably large
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) < 1000:
                logger.warning(
                    f"Downloaded file is too small ({content_length} bytes), likely not the Excel file"
                )
                return False

            # Download to temporary file first
            temp_path = self.local_excel_path.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Verify the downloaded file looks like an Excel file
            if temp_path.stat().st_size < 1000:
                logger.warning("Downloaded file is too small, removing it")
                temp_path.unlink(missing_ok=True)
                return False

            # Move to final location
            temp_path.replace(self.local_excel_path)
            file_size = self.local_excel_path.stat().st_size
            logger.info(
                f"Downloaded Excel file to {self.local_excel_path} ({file_size} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to download Excel file: {e}")
            return False

    def _parse_excel_file(self) -> Optional[List[Dict[str, Any]]]:
        """Parse the Excel file and extract product information."""
        try:
            if not self.local_excel_path.exists():
                logger.error("Excel file does not exist")
                return None

            logger.info("Parsing Excel file...")

            # Read Excel file without assuming header row
            try:
                # First, check what sheets are available
                xl = pd.ExcelFile(self.local_excel_path, engine="openpyxl")
                sheet_name = xl.sheet_names[0]  # Use first sheet

                # Read the entire sheet without headers first to find the actual header row
                df_raw = pd.read_excel(
                    self.local_excel_path,
                    sheet_name=sheet_name,
                    header=None,
                    engine="openpyxl",
                )

                logger.info(f"Read {len(df_raw)} rows from Excel sheet '{sheet_name}'")

                # Find the header row by looking for rows that contain expected column names
                header_row_idx = self._find_header_row(df_raw)
                if header_row_idx is None:
                    logger.error("Could not find header row in Excel file")
                    return None

                logger.info(f"Found header row at index {header_row_idx}")

                # Read the sheet again with the correct header row
                df = pd.read_excel(
                    self.local_excel_path,
                    sheet_name=sheet_name,
                    header=header_row_idx,
                    engine="openpyxl",
                )

                logger.info(f"Columns: {list(df.columns)}")

            except Exception as e:
                logger.error(f"Failed to read Excel file: {e}")
                return None

            products = []

            # Process each row
            for _, row in df.iterrows():
                try:
                    product = self._parse_product_row(row)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {e}")
                    continue

            logger.info(f"Parsed {len(products)} products from Excel file")
            return products

        except Exception as e:
            logger.error(f"Failed to parse Excel file: {e}")
            return None

    def _parse_product_row(self, row) -> Optional[Dict[str, Any]]:
        """Parse a single product row from the Excel file."""
        try:
            # Extract relevant fields - these may need adjustment based on actual Excel structure
            # Common Alko Excel columns typically include:
            # - Nimi (Name)
            # - Numero (Number)
            # - Pullokoko (Bottle size)
            # - Hinta (Price)
            # - Alkoholprosentti (Alcohol %)
            # - Valmistaja (Manufacturer)
            # etc.

            product = {}

            # Try different possible column names (Finnish and English)
            name_cols = ["Nimi", "Name", "Tuote", "Product"]
            number_cols = ["Numero", "Number", "Tuotenumero", "Product Number"]
            size_cols = [
                "Pullokoko",
                "Bottle Size",
                "Koko",
                "Size",
                "Tilavuus",
                "Volume",
            ]
            alcohol_cols = [
                "Alkoholprosentti",
                "Alcohol %",
                "Alkoholi %",
                "Alcohol Percentage",
                "Alkoholi-%",
            ]
            price_cols = ["Hinta", "Price"]

            # Extract name
            for col in name_cols:
                if col in row.index and pd.notna(row[col]):
                    product["name"] = str(row[col]).strip()
                    break

            # Extract number
            for col in number_cols:
                if col in row.index and pd.notna(row[col]):
                    product["number"] = str(row[col]).strip()
                    break

            # Extract bottle size (in liters or cl)
            for col in size_cols:
                if col in row.index and pd.notna(row[col]):
                    size_str = str(row[col]).strip()
                    product["bottle_size"] = self._parse_bottle_size(size_str)
                    product["bottle_size_raw"] = size_str
                    break

            # Extract alcohol percentage
            for col in alcohol_cols:
                if col in row.index and pd.notna(row[col]):
                    alcohol_str = str(row[col]).strip()
                    product["alcohol_percent"] = self._parse_alcohol_percent(
                        alcohol_str
                    )
                    break

            # Extract price
            for col in price_cols:
                if col in row.index and pd.notna(row[col]):
                    price_value = row[col]
                    if isinstance(price_value, (int, float)):
                        product["price"] = float(price_value)
                    break

            # Only return product if we have at least name and alcohol info
            if product.get("name") and (product.get("alcohol_percent") is not None):
                # Calculate alcohol content in grams
                if product.get("bottle_size") and product.get("alcohol_percent"):
                    bottle_size_liters = product["bottle_size"]
                    alcohol_percent = product["alcohol_percent"]
                    # Alcohol content in grams = volume (liters) * 1000 * density (0.789 g/ml) * alcohol % / 100
                    # Density of ethanol is approximately 0.789 g/ml at 20°C
                    # Convert liters to ml, then calculate alcohol mass
                    alcohol_grams = (
                        bottle_size_liters * 1000 * 0.789 * (alcohol_percent / 100)
                    )
                    product["alcohol_grams"] = round(alcohol_grams, 1)

                return product

        except Exception as e:
            logger.warning(f"Failed to parse product row: {e}")

        return None

    def _find_header_row(self, df: pd.DataFrame) -> Optional[int]:
        """
        Find the header row in the Excel file by looking for rows that contain expected column names.

        Args:
            df: Raw DataFrame without headers

        Returns:
            Index of the header row, or None if not found
        """
        # Expected column names to look for (Finnish)
        expected_headers = [
            "Nimi",
            "Numero",
            "Pullokoko",
            "Hinta",
            "Alkoholprosentti",
            "Valmistaja",
            "Tyyppi",
            "Alue",
            "Maa",
            "Vuosi",
            "Väri",
            "Rypäleet",
        ]

        # Check first 20 rows for header-like content
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            row_values = [str(val).strip() for val in row.values if pd.notna(val)]

            # Count how many expected headers are in this row
            matches = 0
            for expected in expected_headers:
                if any(expected.lower() in val.lower() for val in row_values):
                    matches += 1

            # If we find at least 3 expected headers, this is likely the header row
            if matches >= 3:
                logger.info(
                    f"Found header row at index {idx} with {matches} matching headers"
                )
                return idx

        # Fallback: look for rows that don't contain numbers or dates in first column
        # Headers typically don't have numbers
        import re

        for idx in range(min(10, len(df))):
            first_cell = str(df.iloc[idx, 0]).strip()
            # If first cell looks like a header (no numbers, not a date)
            if (
                first_cell
                and not re.search(r"\d", first_cell)  # No digits
                and not re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", first_cell)  # Not a date
                and len(first_cell) < 50
            ):  # Reasonable header length
                logger.info(
                    f"Using fallback header detection at row {idx}: '{first_cell}'"
                )
                return idx

        logger.warning("Could not find header row using any method")
        return None

    def _parse_bottle_size(self, size_str: str) -> Optional[float]:
        """Parse bottle size string and return size in liters."""
        try:
            # Handle various formats like "0.33 l", "33 cl", "330 ml", etc.
            size_str = size_str.lower().strip()

            # Extract numeric value
            import re

            match = re.search(r"(\d+(?:\.\d+)?)", size_str)
            if not match:
                return None

            value = float(match.group(1))

            # Determine unit
            if "l" in size_str or "liter" in size_str:
                return value  # Already in liters
            elif "cl" in size_str:
                return value / 100  # Centiliters to liters
            elif "ml" in size_str:
                return value / 1000  # Milliliters to liters
            else:
                # Assume liters if no unit specified
                return value

        except Exception as e:
            logger.warning(f"Failed to parse bottle size '{size_str}': {e}")
            return None

    def _parse_alcohol_percent(self, alcohol_str: str) -> Optional[float]:
        """Parse alcohol percentage string."""
        try:
            # Extract numeric value, handle formats like "4.7%", "4,7%", "4.7"
            alcohol_str = alcohol_str.strip()
            alcohol_str = alcohol_str.replace(
                ",", "."
            )  # Handle European decimal separator
            alcohol_str = alcohol_str.rstrip("%")  # Remove % sign

            return float(alcohol_str)
        except Exception as e:
            logger.warning(f"Failed to parse alcohol percent '{alcohol_str}': {e}")
            return None

    def update_data(self, force: bool = False) -> bool:
        """
        Update the product data by downloading and parsing the Excel file.

        Args:
            force: Force download even if file appears unchanged

        Returns:
            True if data was updated, False otherwise
        """
        try:
            # Check if we should download
            if not force and not self._should_download_file():
                logger.info("Excel file is up to date, skipping download")
                return False

            # Download the file
            if not self._download_excel_file():
                return False

            # Parse the file
            products = self._parse_excel_file()
            if not products:
                logger.error("Failed to parse any products from Excel file")
                return False

            # Update cache
            self.products_cache = products
            self._save_cache()

            logger.info(f"Successfully updated Alko data with {len(products)} products")
            return True

        except Exception as e:
            logger.error(f"Failed to update Alko data: {e}")
            return False

    def search_products(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for products by name.

        Args:
            query: Search query (case-insensitive partial match)
            limit: Maximum number of results to return

        Returns:
            List of matching products
        """
        # Try to load data if cache is empty but Excel file exists
        if not self.products_cache and self.local_excel_path.exists():
            logger.info("No cached data but Excel file exists, attempting to parse...")
            products = self._parse_excel_file()
            if products:
                self.products_cache = products
                self._save_cache()
                logger.info(
                    f"Successfully loaded {len(products)} products from Excel file"
                )

        if not self.products_cache:
            logger.warning("No product data available")
            return []

        try:
            query_lower = query.lower().strip()
            query_words = query_lower.split()
            matches = []

            for product in self.products_cache:
                name = product.get("name", "").lower()

                # Check if all query words appear in the product name
                if all(word in name for word in query_words):
                    matches.append(product)
                    if len(matches) >= limit:
                        break

            return matches

        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            return []

    def get_product_info(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific product.

        Args:
            query: Product name or number to search for

        Returns:
            Product information dictionary or None if not found
        """
        # Try to load data if cache is empty but Excel file exists
        if not self.products_cache and self.local_excel_path.exists():
            logger.info("No cached data but Excel file exists, attempting to parse...")
            products = self._parse_excel_file()
            if products:
                self.products_cache = products
                self._save_cache()
                logger.info(
                    f"Successfully loaded {len(products)} products from Excel file"
                )

        if not self.products_cache:
            logger.warning("No product data available")
            return None

        matches = self.search_products(query, limit=1)
        return matches[0] if matches else None

    def format_product_info(self, product: Dict[str, Any]) -> str:
        """
        Format product information into a readable message.

        Args:
            product: Product information dictionary

        Returns:
            Formatted message string
        """
        try:
            name = product.get("name", "Unknown")
            bottle_size = product.get("bottle_size_raw", "Unknown")
            alcohol_percent = product.get("alcohol_percent")
            alcohol_grams = product.get("alcohol_grams")
            price = product.get("price")

            parts = [f"🍺 {name}"]

            if bottle_size:
                parts.append(f"Pullokoko: {bottle_size}")

            if alcohol_percent is not None:
                parts.append(f"Alkoholi: {alcohol_percent}%")

            if alcohol_grams is not None:
                parts.append(f"Alkoholia: {alcohol_grams}g")

            if price is not None:
                parts.append(f"Hinta: {price:.2f}€")

            return " | ".join(parts)

        except Exception as e:
            logger.error(f"Failed to format product info: {e}")
            return f"🍺 {product.get('name', 'Unknown product')}"

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the loaded data."""
        if not self.products_cache:
            return {"error": "No data loaded"}

        total_products = len(self.products_cache)
        file_exists = self.local_excel_path.exists()
        file_size = self.local_excel_path.stat().st_size if file_exists else 0
        last_modified = None

        if file_exists:
            try:
                last_modified = datetime.fromtimestamp(
                    self.local_excel_path.stat().st_mtime
                ).isoformat()
            except Exception:
                pass

        return {
            "total_products": total_products,
            "file_exists": file_exists,
            "file_size": file_size,
            "last_modified": last_modified,
            "cache_file": str(self.cache_file),
        }


def create_alko_service() -> AlkoService:
    """
    Factory function to create an Alko service instance.

    Returns:
        AlkoService instance
    """
    return AlkoService()
