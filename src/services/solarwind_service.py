"""
Solar Wind Service Module

Provides solar wind information using NOAA SWPC API.
"""

from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

import requests


class SolarWindService:
    """Service for fetching solar wind information."""

    def __init__(self):
        """Initialize solar wind service."""
        self.plasma_url = (
            "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
        )
        self.mag_url = (
            "https://services.swpc.noaa.gov/products/solar-wind/mag-5-minute.json"
        )

    def get_solar_wind_data(self) -> Dict[str, Any]:
        """
        Get current solar wind information.

        Returns:
            Dictionary containing solar wind information or error details
        """
        try:
            # Defer heavy import to runtime to avoid optional dependency issues
            import pandas as pd

            # Fetch both datasets
            plasma_data = self._fetch_json(self.plasma_url)
            mag_data = self._fetch_json(self.mag_url)

            # Create DataFrames and convert timestamps
            plasma_df = pd.DataFrame(plasma_data[1:], columns=plasma_data[0])
            mag_df = pd.DataFrame(mag_data[1:], columns=mag_data[0])

            plasma_df["time_tag"] = pd.to_datetime(plasma_df["time_tag"], utc=True)
            mag_df["time_tag"] = pd.to_datetime(mag_df["time_tag"], utc=True)

            # Find common timestamps
            common_times = set(plasma_df["time_tag"]).intersection(
                set(mag_df["time_tag"])
            )
            if not common_times:
                return {
                    "error": True,
                    "message": "No common timestamps found between plasma and magnetic field data",
                }

            latest_common_time = max(common_times)

            # Filter rows
            plasma_row = plasma_df[plasma_df["time_tag"] == latest_common_time].iloc[0]
            mag_row = mag_df[mag_df["time_tag"] == latest_common_time].iloc[0]

            # Convert to Finnish time (EET/EEST automatically)
            finland_tz = ZoneInfo("Europe/Helsinki")
            local_time = latest_common_time.astimezone(finland_tz)

            return {
                "error": False,
                "timestamp": local_time.strftime("%Y-%m-%d %H:%M:%S"),
                "density": plasma_row["density"],
                "speed": plasma_row["speed"],
                "temperature": plasma_row["temperature"],
                "magnetic_field": mag_row["bt"],
                "local_time": local_time,
            }

        except Exception as e:
            name = getattr(e, "__class__", type(e)).__name__
            if name == "Timeout":
                return {"error": True, "message": "Solar wind API request timed out"}
            elif name == "ConnectionError":
                return {
                    "error": True,
                    "message": f"Solar wind API connection error: {str(e)}",
                }
            elif name in ("RequestException", "HTTPError"):
                return {
                    "error": True,
                    "message": f"Solar wind API request failed: {str(e)}",
                }
            else:
                return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def _fetch_json(self, url: str) -> Any:
        """
        Fetch and parse JSON data from URL.

        Args:
            url: URL to fetch data from

        Returns:
            Parsed JSON data
        """
        response = requests.get(url, timeout=10)
        # Some mocked responses may not implement raise_for_status
        getattr(response, "raise_for_status", (lambda: None))()
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

        # Get visual indicators for each parameter
        density_indicator = self._get_density_indicator(float(data["density"]))
        speed_indicator = self._get_speed_indicator(float(data["speed"]))
        temp_indicator = self._get_temperature_indicator(float(data["temperature"]))
        mag_indicator = self._get_magnetic_field_indicator(
            float(data["magnetic_field"])
        )

        # Format the data into a single line with indicators
        return (
            f"🌌 Solar Wind ({data['timestamp']}): "
            f"Density: {data['density']}/cm³ {density_indicator} | "
            f"Speed: {data['speed']} km/s {speed_indicator} | "
            f"Temperature: {data['temperature']} K {temp_indicator} | "
            f"Magnetic Field: {data['magnetic_field']} nT {mag_indicator}"
        )

    def _get_density_indicator(self, density: float) -> str:
        """
        Get density visual indicator.

        Args:
            density: Particle density in particles per cm³

        Returns:
            Visual indicator string
        """
        if density < 1:
            return "🟢 C-Hole!"
        elif 1 <= density <= 6:
            return "🟢"  # Green circle
        elif 6 < density <= 20:
            return "🟡"  # Yellow circle
        else:  # > 20
            return "🔴"  # Red circle

    def _get_speed_indicator(self, speed: float) -> str:
        """
        Get speed visual indicator.

        Args:
            speed: Solar wind speed in km/s

        Returns:
            Visual indicator string
        """
        if 400 <= speed <= 600:
            return "🟢"  # Green circle
        elif speed < 400:
            return "🟡"  # Yellow circle
        else:  # > 600
            return "🔴"  # Red circle

    def _get_temperature_indicator(self, temperature: float) -> str:
        """
        Get temperature visual indicator.

        Args:
            temperature: Temperature in Kelvin

        Returns:
            Visual indicator string
        """
        if temperature < 200000:
            return "🟢"  # Green circle
        elif 200000 <= temperature <= 300000:
            return "🟡"  # Yellow circle
        else:  # > 300000
            return "🔴"  # Red circle

    def _get_magnetic_field_indicator(self, magnetic_field: float) -> str:
        """
        Get magnetic field visual indicator.

        Args:
            magnetic_field: Magnetic field strength in nT

        Returns:
            Visual indicator string
        """
        if magnetic_field < 8:
            return "🟢"  # Green circle
        elif 8 <= magnetic_field <= 10:
            return "🟡"  # Yellow circle
        elif 10 < magnetic_field <= 20:
            return "🔴"  # Red circle
        else:  # > 20
            return "☠️"  # Skull and crossbones


def get_solar_wind_info() -> str:
    """
    Get formatted solar wind information.

    Returns:
        Formatted solar wind information string
    """
    service = SolarWindService()
    data = service.get_solar_wind_data()
    return service.format_solar_wind_data(data)
