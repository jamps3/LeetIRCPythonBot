"""
Solar Wind Service Module

Provides solar wind information using NOAA SWPC API.
"""

import requests
import pandas as pd
from datetime import datetime
import pytz
from typing import Dict, Any


class SolarWindService:
    """Service for fetching solar wind information."""

    def __init__(self):
        """Initialize solar wind service."""
        self.plasma_url = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
        self.mag_url = "https://services.swpc.noaa.gov/products/solar-wind/mag-5-minute.json"

    def get_solar_wind_data(self) -> Dict[str, Any]:
        """
        Get current solar wind information.

        Returns:
            Dictionary containing solar wind information or error details
        """
        try:
            # Fetch both datasets
            plasma_data = self._fetch_json(self.plasma_url)
            mag_data = self._fetch_json(self.mag_url)

            # Create DataFrames and convert timestamps
            plasma_df = pd.DataFrame(plasma_data[1:], columns=plasma_data[0])
            mag_df = pd.DataFrame(mag_data[1:], columns=mag_data[0])

            plasma_df["time_tag"] = pd.to_datetime(plasma_df["time_tag"], utc=True)
            mag_df["time_tag"] = pd.to_datetime(mag_df["time_tag"], utc=True)

            # Find common timestamps
            common_times = set(plasma_df["time_tag"]).intersection(set(mag_df["time_tag"]))
            if not common_times:
                return {
                    "error": True,
                    "message": "No common timestamps found between plasma and magnetic field data"
                }

            latest_common_time = max(common_times)

            # Filter rows
            plasma_row = plasma_df[plasma_df["time_tag"] == latest_common_time].iloc[0]
            mag_row = mag_df[mag_df["time_tag"] == latest_common_time].iloc[0]

            # Convert to Finnish time (EET/EEST automatically)
            finland_tz = pytz.timezone("Europe/Helsinki")
            local_time = latest_common_time.astimezone(finland_tz)

            return {
                "error": False,
                "timestamp": local_time.strftime("%Y-%m-%d %H:%M:%S"),
                "density": plasma_row["density"],
                "speed": plasma_row["speed"], 
                "temperature": plasma_row["temperature"],
                "magnetic_field": mag_row["bt"],
                "local_time": local_time
            }

        except requests.exceptions.Timeout:
            return {
                "error": True,
                "message": "Solar wind API request timed out"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "error": True,
                "message": f"Solar wind API connection error: {str(e)}"
            }
        except requests.exceptions.RequestException as e:
            return {
                "error": True,
                "message": f"Solar wind API request failed: {str(e)}"
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Unexpected error: {str(e)}"
            }

    def _fetch_json(self, url: str) -> Any:
        """
        Fetch and parse JSON data from URL.

        Args:
            url: URL to fetch data from

        Returns:
            Parsed JSON data
        """
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def format_solar_wind_data(self, data: Dict[str, Any]) -> str:
        """
        Format solar wind data into a single line for IRC/console output.

        Args:
            data: Solar wind data dictionary

        Returns:
            Formatted string for output
        """
        if data.get("error"):
            return f"❌ Solar Wind Error: {data.get('message', 'Unknown error')}"

        # Format the data into a single line
        return (f"🌌 Solar Wind ({data['timestamp']}): "
                f"Density: {data['density']}/cm³ | "
                f"Speed: {data['speed']} km/s | "
                f"Temperature: {data['temperature']} K | "
                f"Magnetic Field: {data['magnetic_field']} nT")


def get_solar_wind_info() -> str:
    """
    Get formatted solar wind information.
    
    Returns:
        Formatted solar wind information string
    """
    service = SolarWindService()
    data = service.get_solar_wind_data()
    return service.format_solar_wind_data(data)
