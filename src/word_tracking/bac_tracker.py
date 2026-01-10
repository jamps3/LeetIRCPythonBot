"""
BAC (Blood Alcohol Content) Tracker

Tracks BAC levels per user with realistic Widmark formula calculations.
Supports personalized profiles with weight, sex, and custom burn rates.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import logger

from .data_manager import DataManager


class BACTracker:
    """Tracks Blood Alcohol Content for users with realistic Widmark formula calculations."""

    def __init__(self, data_manager: DataManager):
        """
        Initialize the BAC tracker.

        Args:
            data_manager: DataManager instance for data persistence
        """
        self.data_manager = data_manager
        self.logger = logger.get_logger("BACTracker")

        # BAC calculation constants
        self.ABSORPTION_TIME_MINUTES = 20  # Alcohol peaks in ~20 minutes
        self.STANDARD_DRINK_GRAMS = 12.2  # Standard krak = 12.2g pure alcohol

        # Default values for Widmark formula
        self.DEFAULT_BODY_WATER_MALE = 0.68  # for men
        self.DEFAULT_BODY_WATER_FEMALE = 0.55  # for women
        self.DEFAULT_BURN_RATE_MALE = 0.15  # for men (‰/h)
        self.DEFAULT_BURN_RATE_FEMALE = 0.13  # for women (‰/h)
        self.DEFAULT_WEIGHT_KG = 75  # Default weight
        self.DEFAULT_SEX = "m"  # Default to male

    def _load_bac_data(self) -> Dict[str, Dict]:
        """Load BAC data from state.json."""
        state = self.data_manager.load_json(self.data_manager.state_file)
        return state.get("bac_tracking", {})

    def _save_bac_data(self, bac_data: Dict[str, Dict]):
        """Save BAC data to state.json."""
        state = self.data_manager.load_json(self.data_manager.state_file)
        state["bac_tracking"] = bac_data
        self.data_manager.save_json(self.data_manager.state_file, state)

    def _load_user_profiles(self) -> Dict[str, Dict]:
        """Load user profiles (weight, sex, burn rate) from state.json."""
        state = self.data_manager.load_json(self.data_manager.state_file)
        return state.get("bac_profiles", {})

    def _save_user_profiles(self, profiles: Dict[str, Dict]):
        """Save user profiles to state.json."""
        state = self.data_manager.load_json(self.data_manager.state_file)
        state["bac_profiles"] = profiles
        self.data_manager.save_json(self.data_manager.state_file, state)

    def set_user_profile(
        self,
        server: str,
        nick: str,
        weight_kg: Optional[float] = None,
        sex: Optional[str] = None,
        burn_rate: Optional[float] = None,
    ):
        """
        Set user profile for personalized BAC calculations.

        Args:
            server: Server name
            nick: User nickname
            weight_kg: Weight in kilograms (30-300 kg)
            sex: 'm' for male, 'f' for female
            burn_rate: Custom burn rate in ‰ per hour (0.05-1.0)
        """
        profiles = self._load_user_profiles()
        user_key = f"{server}:{nick}"

        if user_key not in profiles:
            profiles[user_key] = {}

        # Validate and set weight
        if weight_kg is not None:
            if 30 <= weight_kg <= 300:
                profiles[user_key]["weight_kg"] = weight_kg
            # If invalid, don't set it (will use default)

        # Validate and set sex
        if sex is not None:
            sex_lower = sex.lower()
            if sex_lower in ["m", "f"]:
                profiles[user_key]["sex"] = sex_lower
            # If invalid, don't set it (will use default)

        # Validate and set burn rate
        if burn_rate is not None:
            if 0.05 <= burn_rate <= 1.0:
                profiles[user_key]["burn_rate"] = burn_rate
            # If invalid, don't set it (will use default)

        self._save_user_profiles(profiles)

    def get_user_profile(self, server: str, nick: str) -> Dict[str, any]:
        """
        Get user's BAC calculation profile.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            Dictionary with weight_kg, sex, burn_rate
        """
        profiles = self._load_user_profiles()
        user_key = f"{server}:{nick}"

        profile = profiles.get(user_key, {})

        weight_kg = profile.get("weight_kg", self.DEFAULT_WEIGHT_KG)
        sex = profile.get("sex", self.DEFAULT_SEX)
        return {
            "weight_kg": weight_kg,
            "sex": sex,
            "burn_rate": profile.get(
                "burn_rate",
                self._get_default_burn_rate(sex, weight_kg),
            ),
        }

    def _get_body_water_constant(self, sex: str) -> float:
        """Get body water constant based on sex."""
        return (
            self.DEFAULT_BODY_WATER_MALE
            if sex.lower() == "m"
            else self.DEFAULT_BODY_WATER_FEMALE
        )

    def _get_default_burn_rate(self, sex: str, weight_kg: float = None) -> float:
        """Get default burn rate based on sex and optionally weight."""
        if weight_kg is None:
            # Fallback to fixed rates for backward compatibility
            return (
                self.DEFAULT_BURN_RATE_MALE
                if sex.lower() == "m"
                else self.DEFAULT_BURN_RATE_FEMALE
            )

        # Calculate weight-based burn rate
        # Base rates per kg of body weight (approximate values)
        base_rate_per_kg_male = 0.0020  # ‰/h per kg for men
        base_rate_per_kg_female = 0.0017  # ‰/h per kg for women

        if sex.lower() == "m":
            burn_rate = weight_kg * base_rate_per_kg_male
        else:
            burn_rate = weight_kg * base_rate_per_kg_female

        # Clamp to reasonable ranges
        min_rate = 0.08  # minimum 0.08‰/h
        max_rate = 0.25  # maximum 0.25‰/h

        return round(max(min_rate, min(max_rate, burn_rate)), 2)

    def get_user_bac(self, server: str, nick: str) -> Dict[str, float]:
        """
        Get current BAC data for a user.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            Dictionary with current_bac, peak_bac, sober_time
        """
        bac_data = self._load_bac_data()
        user_key = f"{server}:{nick}"

        if user_key not in bac_data:
            return {
                "current_bac": 0.0,
                "peak_bac": 0.0,
                "sober_time": None,
                "driving_time": None,
                "last_drink": None,
            }

        user_data = bac_data[user_key]
        current_bac = self._calculate_current_bac(server, nick, user_data)

        # Update stored BAC if it has changed
        if abs(current_bac - user_data.get("current_bac", 0.0)) > 0.001:
            user_data["current_bac"] = current_bac
            user_data["last_update_time"] = time.time()
            self._save_bac_data(bac_data)

        peak_bac = user_data.get("peak_bac", 0.0)
        sober_time = self._calculate_sober_time(server, nick, current_bac)
        driving_time = self._calculate_driving_time(server, nick, current_bac)

        return {
            "current_bac": round(current_bac, 2),
            "peak_bac": round(peak_bac, 2),
            "sober_time": sober_time,
            "driving_time": driving_time,
            "last_drink": user_data.get("last_drink"),
        }

    def _calculate_current_bac(self, server: str, nick: str, user_data: Dict) -> float:
        """
        Calculate current BAC based on last update time and burn rate.

        Args:
            server: Server name
            nick: User nickname
            user_data: User's BAC data

        Returns:
            Current BAC value
        """
        current_bac = user_data.get("current_bac", 0.0)
        last_update = user_data.get("last_update_time", time.time())

        # Calculate time elapsed since last update
        time_elapsed_hours = (time.time() - last_update) / 3600.0

        # Get user's burn rate from profile
        profile = self.get_user_profile(server, nick)
        burn_rate_per_mille = profile["burn_rate"]  # ‰/hour

        # Apply burn-off rate
        burned_alcohol = time_elapsed_hours * burn_rate_per_mille
        current_bac = max(0.0, current_bac - burned_alcohol)

        return current_bac

    def _calculate_sober_time(
        self, server: str, nick: str, current_bac: float
    ) -> Optional[str]:
        """
        Calculate estimated time when BAC reaches 0.

        Args:
            server: Server name
            nick: User nickname
            current_bac: Current BAC value

        Returns:
            Formatted time string or None if already sober
        """
        if current_bac <= 0.0:
            return None

        # Get user's burn rate from profile
        profile = self.get_user_profile(server, nick)
        burn_rate_per_mille = profile["burn_rate"]  # ‰/hour

        # Calculate hours until sober
        hours_until_sober = current_bac / burn_rate_per_mille
        sober_datetime = datetime.now() + timedelta(hours=hours_until_sober)

        return sober_datetime.strftime("%H:%M")

    def _calculate_driving_time(
        self, server: str, nick: str, current_bac: float
    ) -> Optional[str]:
        """
        Calculate estimated time when BAC reaches legal driving limit (0.5‰).

        Args:
            server: Server name
            nick: User nickname
            current_bac: Current BAC value

        Returns:
            Formatted time string or None if already below limit
        """
        legal_limit = 0.5  # ‰ - Finnish legal driving limit

        if current_bac <= legal_limit:
            return None

        # Get user's burn rate from profile
        profile = self.get_user_profile(server, nick)
        burn_rate_per_mille = profile["burn_rate"]  # ‰/hour

        # Calculate hours until legal limit
        bac_above_limit = current_bac - legal_limit
        hours_until_driving = bac_above_limit / burn_rate_per_mille
        driving_datetime = datetime.now() + timedelta(hours=hours_until_driving)

        return driving_datetime.strftime("%H:%M")

    def add_drink(
        self, server: str, nick: str, drink_grams: float = None, opened_time: str = None
    ) -> Dict[str, float]:
        """
        Add a drink to user's BAC calculation.

        Args:
            server: Server name
            nick: User nickname
            drink_grams: Grams of pure alcohol (default: standard drink)
            opened_time: Time when drink was opened in HH:MM format (optional)

        Returns:
            Updated BAC information
        """
        if drink_grams is None:
            drink_grams = self.STANDARD_DRINK_GRAMS

        bac_data = self._load_bac_data()
        user_key = f"{server}:{nick}"

        if user_key not in bac_data:
            bac_data[user_key] = {
                "current_bac": 0.0,
                "peak_bac": 0.0,
                "last_update_time": time.time(),
                "last_drink": datetime.now().isoformat(),
                "last_drink_grams": drink_grams,
                "pending_alcohol": 0.0,
            }

        user_data = bac_data[user_key]

        # Update current BAC (burn off any alcohol since last update)
        current_bac = self._calculate_current_bac(server, nick, user_data)

        # If opened_time is provided, calculate how much alcohol has already burned
        effective_drink_grams = drink_grams
        if opened_time:
            try:
                # Parse the opened time
                opened_datetime = datetime.strptime(opened_time, "%H:%M")
                # Assume it's today
                opened_datetime = opened_datetime.replace(
                    year=datetime.now().year,
                    month=datetime.now().month,
                    day=datetime.now().day,
                )

                # Calculate time elapsed since opening
                now = datetime.now()
                if opened_datetime > now:
                    # If opened time is in the future, assume it's yesterday
                    opened_datetime = opened_datetime.replace(
                        day=opened_datetime.day - 1
                    )

                time_elapsed_hours = (now - opened_datetime).total_seconds() / 3600.0

                # Get user's burn rate
                profile = self.get_user_profile(server, nick)
                burn_rate_per_mille = profile["burn_rate"]  # ‰/hour

                # Calculate how much BAC would have been burned
                # First calculate what the BAC increase would have been initially
                body_water = (
                    self._get_body_water_constant(profile["sex"]) * profile["weight_kg"]
                )
                initial_bac_increase = drink_grams / body_water  # ‰

                # Calculate burned BAC during elapsed time
                burned_bac = min(
                    initial_bac_increase, time_elapsed_hours * burn_rate_per_mille
                )

                # Effective remaining alcohol
                remaining_bac = initial_bac_increase - burned_bac
                effective_drink_grams = remaining_bac * body_water

                self.logger.debug(
                    f"Drink opened at {opened_time}, elapsed {time_elapsed_hours:.1f}h, "
                    f"burned BAC {burned_bac:.3f}‰, effective grams {effective_drink_grams:.1f}g "
                    f"(was {drink_grams:.1f}g)"
                )

                # Ensure effective_drink_grams doesn't go negative
                effective_drink_grams = max(0.0, effective_drink_grams)

            except ValueError as e:
                self.logger.warning(f"Invalid opened_time format '{opened_time}': {e}")
                # Fall back to full drink_grams

        # Calculate BAC increase using effective alcohol content
        profile = self.get_user_profile(server, nick)
        body_water = (
            self._get_body_water_constant(profile["sex"]) * profile["weight_kg"]
        )
        added_bac = effective_drink_grams / (body_water)  # ‰

        self.logger.debug(
            f"effective_drink_grams={effective_drink_grams:.3f} body_water={body_water:.3f} added_bac={added_bac:.3f} profile={profile}"
        )

        # Calculate peak BAC (current + new drink, assuming immediate absorption for peak)
        peak_bac = current_bac + added_bac

        # For more realism, we could implement absorption over time,
        # but for simplicity, we'll assume drinks are consumed and absorbed immediately
        current_bac = peak_bac
        user_data["peak_bac"] = max(user_data.get("peak_bac", 0.0), peak_bac)

        # Update timestamps and last drink info
        user_data["current_bac"] = current_bac
        user_data["last_update_time"] = time.time()
        user_data["last_drink"] = datetime.now().isoformat()
        user_data["last_drink_grams"] = drink_grams  # Store original grams

        self._save_bac_data(bac_data)

        # Return the BAC data directly instead of calling get_user_bac again
        # to avoid any timing issues with the burn-off calculation
        sober_time = self._calculate_sober_time(server, nick, current_bac)
        driving_time = self._calculate_driving_time(server, nick, current_bac)

        return {
            "current_bac": round(current_bac, 2),
            "peak_bac": round(peak_bac, 2),
            "sober_time": sober_time,
            "driving_time": driving_time,
            "last_drink": user_data.get("last_drink"),
        }

    def format_bac_message(self, server: str, nick: str) -> str:
        """
        Format BAC information for display to user.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            Formatted BAC message
        """
        self.logger.debug(
            f"Formatting BAC message for server='{server}', nick='{nick}'"
        )

        bac_info = self.get_user_bac(server, nick)

        current = bac_info["current_bac"]
        peak = bac_info["peak_bac"]
        sober_time = bac_info["sober_time"]
        driving_time = bac_info["driving_time"]

        # Get last drink grams from stored data
        bac_data = self._load_bac_data()
        user_key = f"{server}:{nick}"
        user_data = bac_data.get(user_key, {})
        last_drink_grams = user_data.get("last_drink_grams")

        self.logger.debug(
            f"user_key='{user_key}', last_drink_grams={last_drink_grams}, bac_data_keys={list(bac_data.keys())}"
        )

        if current <= 0.0:
            message = f"{nick}: 🍺 Promilles: 0.00‰ (sober)"
            # Include last drink alcohol content even when sober
            if last_drink_grams:
                message += f" | Last: {last_drink_grams:.1f}g"
                self.logger.debug(
                    f"Added last drink grams to sober message: {last_drink_grams}"
                )
            else:
                self.logger.debug("No last_drink_grams found for sober user")
            return message

        message = f"{nick}: 🍺 Promilles: {current:.2f}‰"

        # Get burn rate from profile (only show burn rate, not sex/weight)
        profile = self.get_user_profile(server, nick)
        burn_rate = profile["burn_rate"]
        message += f" | Burn rate: {burn_rate:.2f}‰/h"

        if peak > current:
            message += f" | Peak: {peak:.2f}‰"

        # Include last drink alcohol content if available
        if last_drink_grams:
            message += f" | Last: {last_drink_grams:.1f}g"

        if sober_time:
            message += f" | Sober: ~{sober_time}"

        if driving_time:
            message += f" | Driving: ~{driving_time}"

        # Add warnings for high BAC
        if current >= 1.0:
            message += " ⚠️ Careful!"
        elif current >= 0.5:
            message += " 🍺 Feeling good!"

        return message

    def reset_user_bac(self, server: str, nick: str):
        """
        Reset user's BAC (for testing or manual override).

        Args:
            server: Server name
            nick: User nickname
        """
        bac_data = self._load_bac_data()
        user_key = f"{server}:{nick}"

        if user_key in bac_data:
            del bac_data[user_key]
            self._save_bac_data(bac_data)

    def get_bac_stats(self, server: str) -> Dict[str, any]:
        """
        Get BAC statistics for a server.

        Args:
            server: Server name

        Returns:
            Statistics about active BAC users
        """
        bac_data = self._load_bac_data()
        server_prefix = f"{server}:"

        active_users = []
        for user_key, user_data in bac_data.items():
            if user_key.startswith(server_prefix):
                nick = user_key[len(server_prefix) :]  # noqa E203
                current_bac = self._calculate_current_bac(server, nick, user_data)
                if current_bac > 0.0:
                    active_users.append(
                        {
                            "nick": nick,
                            "bac": round(current_bac, 2),
                            "peak": round(user_data.get("peak_bac", 0.0), 2),
                        }
                    )

        # Sort by BAC descending
        active_users.sort(key=lambda x: x["bac"], reverse=True)

        return {
            "active_users": active_users[:10],  # Top 10
            "total_active": len(active_users),
        }
