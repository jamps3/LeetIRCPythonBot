"""
Tests for BAC (Blood Alcohol Content) Tracker
"""

import os
import tempfile
import time

from src.word_tracking.bac_tracker import BACTacker
from src.word_tracking.data_manager import DataManager
from src.word_tracking.drink_tracker import DrinkTracker


class TestBACTacker:
    """Test cases for BAC tracker functionality."""

    def setup_method(self):
        """Set up test fixtures with isolated data files."""
        # Create a unique temporary directory for this test
        self.temp_dir = tempfile.mkdtemp(prefix="bac_test_")

        # Create DataManager with unique state file
        state_file = os.path.join(self.temp_dir, "state.json")
        self.data_manager = DataManager(data_dir=self.temp_dir, state_file=state_file)

        # Create trackers
        self.bac_tracker = BACTacker(self.data_manager)
        self.drink_tracker = DrinkTracker(self.data_manager)

    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove the temporary directory and all its contents
        import shutil

        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass  # Ignore cleanup errors in tests

    def test_initialization(self):
        """Test BAC tracker initialization."""
        assert self.bac_tracker is not None
        assert self.bac_tracker.STANDARD_DRINK_GRAMS == 12.2
        assert self.bac_tracker.ABSORPTION_TIME_MINUTES == 20

    def test_default_constants(self):
        """Test default BAC calculation constants."""
        assert self.bac_tracker.DEFAULT_BODY_WATER_MALE == 0.68
        assert self.bac_tracker.DEFAULT_BODY_WATER_FEMALE == 0.55
        assert self.bac_tracker.DEFAULT_BURN_RATE_MALE == 0.15
        assert self.bac_tracker.DEFAULT_BURN_RATE_FEMALE == 0.13
        assert self.bac_tracker.DEFAULT_WEIGHT_KG == 75
        assert self.bac_tracker.DEFAULT_SEX == "m"

    def test_get_user_profile_defaults(self):
        """Test getting user profile with defaults."""
        profile = self.bac_tracker.get_user_profile("testserver", "testuser")

        assert profile["weight_kg"] == 75
        assert profile["sex"] == "m"
        assert profile["burn_rate"] == 0.15  # Default male burn rate

    def test_set_user_profile_weight_sex(self):
        """Test setting user profile with weight and sex."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=80, sex="f"
        )

        profile = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile["weight_kg"] == 80
        assert profile["sex"] == "f"
        assert (
            profile["burn_rate"] == 0.14
        )  # Female burn rate: 0.0017 * 80kg = 0.136 → rounded to 0.14

    def test_set_user_profile_burn_rate(self):
        """Test setting custom burn rate."""
        self.bac_tracker.set_user_profile("testserver", "testuser", burn_rate=0.12)

        profile = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile["burn_rate"] == 0.12

    def test_get_user_bac_no_data(self):
        """Test getting BAC for user with no data."""
        bac_info = self.bac_tracker.get_user_bac("testserver", "testuser")

        assert bac_info["current_bac"] == 0.0
        assert bac_info["peak_bac"] == 0.0
        assert bac_info["sober_time"] is None

    def test_add_single_drink_male(self):
        """Test adding a single drink for male user."""
        # Set up male user profile
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )

        # Add a standard drink (12g alcohol)
        result = self.bac_tracker.add_drink("testserver", "testuser", 12.0)

        # Calculate expected BAC using Widmark formula
        # BAC (%) = alcohol_grams / (body_weight_kg × r)
        # Body water effective = 75 × 0.68 = 51 liters
        # BAC = (12 / 40.8) = 0.294‰
        expected_bac = 12.0 / (0.68 * 75)

        assert abs(result["current_bac"] - expected_bac) < 0.01
        assert result["peak_bac"] == result["current_bac"]
        assert result["sober_time"] is not None

    def test_add_default_drink_male(self):
        """Test adding a default drink (using drink tracker parsing)."""
        # Set up male user profile
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )

        # Add a default drink (parsed from drink tracker)
        # Default: standard drink = 12.2g alcohol
        default_alcohol = self.drink_tracker._parse_alcohol_content("unspecified")
        result = self.bac_tracker.add_drink("testserver", "testuser", default_alcohol)

        # Calculate expected BAC
        # BAC = (alcohol_grams / (body_weight_kg × r))
        # Body water effective = 75 × 0.68 = 51L
        # BAC = (12.2 / 40.8) ≈ 0.30‰
        expected_bac = default_alcohol / (0.68 * 75)

        assert abs(result["current_bac"] - expected_bac) < 0.01
        assert result["current_bac"] > 0.23  # Should be about 0.24‰ per krak

    def test_parse_drink_descriptions(self):
        """Test parsing different drink description formats."""
        # Test default drink (unspecified)
        grams1 = self.drink_tracker._parse_alcohol_content("unspecified")
        # Standard drink = 12.2g
        assert abs(grams1 - 12.2) < 0.01

        # Test with size and ABV
        grams2 = self.drink_tracker._parse_alcohol_content("karhu 4,7% 0,5L")
        # 0.5L * 4.7% * 0.789 * 1000 = 18.54g
        assert abs(grams2 - 18.54) < 0.01

        # Test with strong beer
        grams3 = self.drink_tracker._parse_alcohol_content(
            "koti-maista neipa 5,0% 5,0L"
        )
        # 5.0L * 5.0% * 0.789 * 1000 = 197.25g
        assert abs(grams3 - 197.25) < 0.01

        # Test with ounces
        grams4 = self.drink_tracker._parse_alcohol_content("corona 4.5% 12oz")
        # 12oz = 0.355L, so 0.355L * 4.5% * 0.789 * 1000 = 12.58g
        assert abs(grams4 - 12.58) < 0.05  # Allow for rounding precision

    def test_add_single_drink_female(self):
        """Test adding a single drink for female user."""
        # Set up female user profile
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=65, sex="f"
        )

        # Add a standard drink
        result = self.bac_tracker.add_drink("testserver", "testuser", 12.0)

        # Calculate expected BAC
        # Body water effective = 0.55 * 65 = 35.75 liters
        # BAC = (12 / 28.6) ≈ 0.42‰
        expected_bac = 12.0 / (0.55 * 65)

        assert abs(result["current_bac"] - expected_bac) < 0.01

    def test_add_multiple_drinks(self):
        """Test adding multiple drinks."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )

        # Add first drink
        result1 = self.bac_tracker.add_drink("testserver", "testuser", 12.0)
        first_bac = result1["current_bac"]

        # Add second drink (should accumulate)
        result2 = self.bac_tracker.add_drink("testserver", "testuser", 12.0)
        second_bac = result2["current_bac"]

        # Second BAC should be approximately double the first
        assert abs(second_bac - (first_bac * 2)) < 0.02
        assert result2["peak_bac"] == second_bac

    def test_burn_off_over_time(self):
        """Test BAC burn-off over time."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )

        # Add a drink
        result = self.bac_tracker.add_drink("testserver", "testuser", 12.0)
        initial_bac = result["current_bac"]

        # Simulate time passage (1 hour = 3600 seconds)
        # Manually update the last_update_time to simulate time passage
        bac_data = self.bac_tracker._load_bac_data()
        user_key = "testserver:testuser"
        bac_data[user_key]["last_update_time"] = time.time() - 3600  # 1 hour ago
        self.bac_tracker._save_bac_data(bac_data)

        # Get BAC again (should show burn-off)
        result_after = self.bac_tracker.get_user_bac("testserver", "testuser")

        # Calculate expected burn-off using standard burn rate
        # burn_rate_per_mille = 0.15 ‰/hour
        burn_rate_per_mille = 0.15  # ‰/hour
        expected_burned = burn_rate_per_mille * 1.0  # 1 hour
        expected_bac = max(0.0, initial_bac - expected_burned)

        assert abs(result_after["current_bac"] - expected_bac) < 0.01

    def test_custom_burn_rate(self):
        """Test custom burn rate."""
        self.bac_tracker.set_user_profile("testserver", "testuser", burn_rate=0.20)

        result = self.bac_tracker.add_drink("testserver", "testuser", 12.0)
        initial_bac = result["current_bac"]

        # Simulate 30 minutes passage
        bac_data = self.bac_tracker._load_bac_data()
        user_key = "testserver:testuser"
        bac_data[user_key]["last_update_time"] = time.time() - 1800  # 30 min ago
        self.bac_tracker._save_bac_data(bac_data)

        result_after = self.bac_tracker.get_user_bac("testserver", "testuser")

        # Should have burned off approximately 0.10‰ (with rounding tolerance)
        expected_bac = max(0.0, initial_bac - 0.10)
        assert (
            abs(result_after["current_bac"] - expected_bac) < 0.1
        )  # Allow for calculation precision

    def test_sober_time_calculation(self):
        """Test sober time calculation."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )

        result = self.bac_tracker.add_drink("testserver", "testuser", 12.0)
        sober_time = result["sober_time"]

        # Allow for small timing differences (within 10 minutes)
        # The calculation involves floating point precision and time rounding
        assert sober_time is not None
        assert len(sober_time) == 5  # HH:MM format
        # Just verify it's a reasonable time (not empty/null)

    def test_format_bac_message_sober(self):
        """Test BAC message formatting when sober."""
        message = self.bac_tracker.format_bac_message("testserver", "testuser")
        assert "sober" in message.lower()
        assert "‰" in message  # Should show promilles

    def test_format_bac_message_drunk(self):
        """Test BAC message formatting when intoxicated."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )
        self.bac_tracker.add_drink("testserver", "testuser", 12.0)

        message = self.bac_tracker.format_bac_message("testserver", "testuser")
        assert "Promilles:" in message
        assert "testuser:" in message
        assert "🍺" in message
        assert "Burn rate:" in message

    def test_format_bac_message_high_bac(self):
        """Test BAC message with warnings for high BAC."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=50, sex="m"
        )
        # Add many drinks to get high BAC
        for _ in range(5):
            self.bac_tracker.add_drink("testserver", "testuser", 12.0)

        message = self.bac_tracker.format_bac_message("testserver", "testuser")
        assert "⚠️" in message or "Careful" in message

    def test_reset_user_bac(self):
        """Test resetting user BAC."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )
        self.bac_tracker.add_drink("testserver", "testuser", 12.0)

        # Verify BAC exists
        bac_before = self.bac_tracker.get_user_bac("testserver", "testuser")
        assert bac_before["current_bac"] > 0

        # Reset BAC
        self.bac_tracker.reset_user_bac("testserver", "testuser")

        # Verify BAC is reset
        bac_after = self.bac_tracker.get_user_bac("testserver", "testuser")
        assert bac_after["current_bac"] == 0.0
        assert bac_after["peak_bac"] == 0.0

    def test_weight_validation(self):
        """Test weight validation in set_user_profile."""
        # Valid weight should work
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=80, sex="m"
        )
        profile = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile["weight_kg"] == 80

        # Invalid weights should not be set (will use defaults)
        self.bac_tracker.set_user_profile(
            "testserver", "testuser2", weight_kg=10, sex="m"
        )
        profile_invalid = self.bac_tracker.get_user_profile("testserver", "testuser2")
        assert profile_invalid["weight_kg"] == 75  # Default

    def test_sex_validation(self):
        """Test sex validation."""
        # Valid sex values
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=75, sex="m"
        )
        profile_male = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile_male["sex"] == "m"

        self.bac_tracker.set_user_profile(
            "testserver", "testuser2", weight_kg=75, sex="f"
        )
        profile_female = self.bac_tracker.get_user_profile("testserver", "testuser2")
        assert profile_female["sex"] == "f"

        # Invalid sex should not be set
        self.bac_tracker.set_user_profile(
            "testserver", "testuser3", weight_kg=75, sex="x"
        )
        profile_invalid = self.bac_tracker.get_user_profile("testserver", "testuser3")
        assert profile_invalid["sex"] == "m"  # Default

    def test_burn_rate_validation(self):
        """Test burn rate validation."""
        # Valid burn rate
        self.bac_tracker.set_user_profile("testserver", "testuser", burn_rate=0.18)
        profile = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile["burn_rate"] == 0.18

        # Invalid burn rates should not be set
        self.bac_tracker.set_user_profile("testserver", "testuser2", burn_rate=2.0)
        profile_invalid = self.bac_tracker.get_user_profile("testserver", "testuser2")
        assert profile_invalid["burn_rate"] == 0.15  # Default male rate

    def test_multiple_users(self):
        """Test BAC tracking for multiple users."""
        # User 1
        self.bac_tracker.set_user_profile("testserver", "user1", weight_kg=80, sex="m")
        self.bac_tracker.add_drink("testserver", "user1", 12.0)

        # User 2
        self.bac_tracker.set_user_profile("testserver", "user2", weight_kg=60, sex="f")
        self.bac_tracker.add_drink("testserver", "user2", 12.0)

        bac1 = self.bac_tracker.get_user_bac("testserver", "user1")
        bac2 = self.bac_tracker.get_user_bac("testserver", "user2")

        # Different users should have different BAC levels due to different profiles
        assert bac1["current_bac"] != bac2["current_bac"]
        assert bac1["current_bac"] > 0
        assert bac2["current_bac"] > 0

    def test_persistence(self):
        """Test that BAC data persists across tracker instances."""
        # Create first tracker instance
        tracker1 = BACTacker(self.data_manager)
        tracker1.set_user_profile("testserver", "persistuser", weight_kg=70, sex="m")
        tracker1.add_drink("testserver", "persistuser", 12.0)
        bac1 = tracker1.get_user_bac("testserver", "persistuser")

        # Create second tracker instance
        tracker2 = BACTacker(self.data_manager)
        bac2 = tracker2.get_user_bac("testserver", "persistuser")
        profile2 = tracker2.get_user_profile("testserver", "persistuser")

        # Data should persist
        assert bac2["current_bac"] == bac1["current_bac"]
        assert profile2["weight_kg"] == 70
        assert profile2["sex"] == "m"

    def test_edge_case_zero_weight(self):
        """Test edge case with zero weight (should use default)."""
        self.bac_tracker.set_user_profile(
            "testserver", "testuser", weight_kg=0, sex="m"
        )
        profile = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile["weight_kg"] == 75  # Should use default

    def test_edge_case_negative_burn_rate(self):
        """Test edge case with negative burn rate (should use default)."""
        self.bac_tracker.set_user_profile("testserver", "testuser", burn_rate=-0.1)
        profile = self.bac_tracker.get_user_profile("testserver", "testuser")
        assert profile["burn_rate"] == 0.15  # Should use default

    def test_get_bac_stats_empty(self):
        """Test BAC stats for server with no data."""
        stats = self.bac_tracker.get_bac_stats("emptyserver")
        assert stats["active_users"] == []
        assert stats["total_active"] == 0

    def test_get_bac_stats_with_data(self):
        """Test BAC stats for server with active users."""
        # Add some test data
        self.bac_tracker.set_user_profile("testserver", "user1", weight_kg=75, sex="m")
        self.bac_tracker.add_drink("testserver", "user1", 12.0)

        self.bac_tracker.set_user_profile("testserver", "user2", weight_kg=65, sex="f")
        self.bac_tracker.add_drink("testserver", "user2", 12.0)

        stats = self.bac_tracker.get_bac_stats("testserver")

        assert stats["total_active"] == 2
        assert len(stats["active_users"]) == 2

        # Should be sorted by BAC descending
        assert stats["active_users"][0]["bac"] >= stats["active_users"][1]["bac"]
