"""Tests for the Dream Service."""

import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from services.dream_service import DreamService


class TestDreamService(unittest.TestCase):
    """Test cases for DreamService."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.dream_vocab_file = os.path.join(self.temp_dir, "dream_vocab.json")
        self.state_file = os.path.join(self.temp_dir, "state.json")

        # Create mock data manager
        self.mock_data_manager = Mock()
        self.mock_data_manager.load_general_words_data.return_value = {
            "servers": {
                "test_server": {
                    "nicks": {
                        "testuser": {
                            "general_words": {"hello": 5, "world": 3, "test": 2},
                            "total_words": 10,
                        }
                    }
                }
            }
        }
        self.mock_data_manager.load_drink_data.return_value = {
            "servers": {
                "test_server": {
                    "nicks": {
                        "testuser": {
                            "drink_words": {
                                "beer": {"count": 3},
                                "coffee": {"count": 2},
                            }
                        }
                    }
                }
            }
        }
        self.mock_data_manager.load_state.return_value = {"lag_history": []}
        self.mock_data_manager.save_state = Mock()

        # Create mock GPT service
        self.mock_gpt_service = Mock()

        # Create dream service
        self.dream_service = DreamService(
            self.mock_data_manager,
            self.mock_gpt_service,
            self.dream_vocab_file,
            self.state_file,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_dream_vocab_default(self):
        """Test loading default dream vocabulary."""
        vocab = self.dream_service._load_dream_vocab()

        self.assertIn("surrealist", vocab)
        self.assertIn("cyberpunk", vocab)

        # Check surrealist vocabulary
        surrealist_vocab = vocab["surrealist"]
        self.assertIn("nouns", surrealist_vocab)
        self.assertIn("verbs", surrealist_vocab)
        self.assertIn("adjectives", surrealist_vocab)
        self.assertIn("connectors", surrealist_vocab)

        # Check cyberpunk vocabulary
        cyberpunk_vocab = vocab["cyberpunk"]
        self.assertIn("nouns", cyberpunk_vocab)
        self.assertIn("verbs", cyberpunk_vocab)
        self.assertIn("adjectives", cyberpunk_vocab)
        self.assertIn("connectors", cyberpunk_vocab)

    def test_get_daily_conversation_data(self):
        """Test extracting daily conversation data."""
        from datetime import datetime

        data = self.dream_service._get_daily_conversation_data(
            "test_server", datetime.now()
        )

        self.assertEqual(data["server"], "test_server")
        self.assertEqual(data["total_messages"], 10)
        self.assertEqual(data["unique_users"], 1)
        self.assertIn("top_words", data)
        self.assertIn("top_drinks", data)

    def test_generate_surrealist_narrative(self):
        """Test generating surrealist dream narrative."""
        data = {
            "server": "test_server",
            "date": "2026-03-04",
            "total_messages": 10,
            "unique_users": 1,
            "top_words": [("hello", 5), ("world", 3), ("test", 2)],
            "top_drinks": [("beer", 3), ("coffee", 2)],
            "night_percentage": 30,
            "users": ["testuser"],
        }

        narrative = self.dream_service._generate_surrealist_narrative(
            data, self.dream_service.vocab["surrealist"]
        )

        self.assertIsInstance(narrative, str)
        self.assertTrue(len(narrative) > 0)
        # Check that it's not the empty data message
        self.assertNotIn("digital unconscious remains silent", narrative)

    def test_generate_cyberpunk_narrative(self):
        """Test generating cyberpunk dream narrative."""
        data = {
            "server": "test_server",
            "date": "2026-03-04",
            "total_messages": 10,
            "unique_users": 1,
            "top_words": [("hello", 5), ("world", 3), ("test", 2)],
            "top_drinks": [("beer", 3), ("coffee", 2)],
            "night_percentage": 30,
            "users": ["testuser"],
        }

        narrative = self.dream_service._generate_cyberpunk_narrative(
            data, self.dream_service.vocab["cyberpunk"]
        )

        self.assertIsInstance(narrative, str)
        self.assertIn("test_server", narrative)
        self.assertIn("SYSTEM", narrative)
        self.assertIn("hello", narrative)

    def test_generate_technical_report(self):
        """Test generating technical report."""
        data = {
            "server": "test_server",
            "date": "2026-03-04",
            "total_messages": 10,
            "unique_users": 1,
            "top_words": [("hello", 5), ("world", 3), ("test", 2)],
            "top_drinks": [("beer", 3), ("coffee", 2)],
            "night_percentage": 30,
            "users": ["testuser"],
        }

        report = self.dream_service._generate_technical_report(data, "surrealist")

        self.assertIsInstance(report, str)
        self.assertIn("DREAM ANALYSIS REPORT", report)
        self.assertIn("test_server", report)
        self.assertIn("Total Messages: 10", report)
        self.assertIn("Unique Users: 1", report)

    def test_toggle_dream_channel(self):
        """Test toggling dream channel."""
        # Mock state loading and saving
        self.mock_data_manager.load_state.return_value = {"dream_channels": []}

        # Enable channel
        enabled = self.dream_service.toggle_dream_channel("#test")
        self.assertTrue(enabled)

        # Disable channel
        enabled = self.dream_service.toggle_dream_channel("#test")
        self.assertFalse(enabled)

    def test_is_dream_channel_enabled(self):
        """Test checking if dream channel is enabled."""
        self.mock_data_manager.load_state.return_value = {
            "dream_channels": ["#test", "#other"]
        }

        self.assertTrue(self.dream_service.is_dream_channel_enabled("#test"))
        self.assertFalse(self.dream_service.is_dream_channel_enabled("#nonexistent"))

    def test_get_enabled_channels(self):
        """Test getting enabled channels."""
        self.mock_data_manager.load_state.return_value = {
            "dream_channels": ["#test", "#other"]
        }

        channels = self.dream_service.get_enabled_channels()
        self.assertEqual(set(channels), {"#test", "#other"})

    def test_measure_and_store_lag(self):
        """Test measuring and storing lag."""
        lag_ns = 150000000  # 150ms in nanoseconds

        self.dream_service.measure_and_store_lag(lag_ns)

        # Verify state was saved
        self.mock_data_manager.save_state.assert_called_once()
        saved_state = self.mock_data_manager.save_state.call_args[0][0]
        self.assertIn("lag_history", saved_state)
        self.assertEqual(len(saved_state["lag_history"]), 1)
        self.assertEqual(saved_state["lag_history"][0]["lag_ns"], lag_ns)

    def test_get_average_lag(self):
        """Test getting average lag from history."""
        lag_history = [
            {"timestamp": "2026-03-04T23:59:50", "lag_ns": 150000000},
            {"timestamp": "2026-03-04T23:59:51", "lag_ns": 145000000},
            {"timestamp": "2026-03-04T23:59:52", "lag_ns": 155000000},
        ]
        self.mock_data_manager.load_state.return_value = {"lag_history": lag_history}

        avg_lag = self.dream_service._get_average_lag()
        expected_avg = (150000000 + 145000000 + 155000000) / 3
        self.assertEqual(avg_lag, expected_avg)

    def test_generate_dream_surrealist(self):
        """Test generating a complete surrealist dream."""
        dream = self.dream_service.generate_dream(
            "test_server", "#test", "surrealist", "narrative"
        )

        self.assertIsInstance(dream, str)
        self.assertIn("Generated for #test", dream)

    def test_generate_dream_cyberpunk(self):
        """Test generating a complete cyberpunk dream."""
        dream = self.dream_service.generate_dream(
            "test_server", "#test", "cyberpunk", "narrative"
        )

        self.assertIsInstance(dream, str)
        self.assertIn("test_server", dream)
        self.assertIn("SYSTEM", dream)
        self.assertIn("Generated for #test", dream)

    def test_generate_dream_report(self):
        """Test generating a technical report dream."""
        dream = self.dream_service.generate_dream(
            "test_server", "#test", "surrealist", "report"
        )

        self.assertIsInstance(dream, str)
        self.assertIn("DREAM ANALYSIS REPORT", dream)
        self.assertIn("test_server", dream)
        self.assertIn("Generated for #test", dream)


if __name__ == "__main__":
    unittest.main()
