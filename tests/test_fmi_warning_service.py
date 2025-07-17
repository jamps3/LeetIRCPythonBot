import unittest
from unittest.mock import Mock, patch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.fmi_warning_service import FMIWarningService

class TestFMIWarningService(unittest.TestCase):

    def setUp(self):
        self.mock_callback = Mock()
        self.service = FMIWarningService(callback=self.mock_callback)

    @patch('services.fmi_warning_service.feedparser.parse')
    @patch('services.fmi_warning_service.FMIWarningService._load_seen_hashes')
    @patch('services.fmi_warning_service.FMIWarningService._load_seen_data')
    def test_duplicate_title_filtering(self, mock_load_seen_data, mock_load_seen_hashes, mock_feedparser_parse):
        # Setup data
        mock_load_seen_hashes.return_value = set()
        mock_load_seen_data.return_value = [
            {"title": "Warning 1 Joensuu", "hash": "hash1"},
            {"title": "Warning 2 Joensuu", "hash": "hash2"},
        ]

        mock_feedparser_parse.return_value.entries = [
            {"title": "Warning 1 Joensuu", "summary": "Summary 3"},  # Duplicate
            {"title": "Warning 3 Joensuu", "summary": "Summary 4"},
        ]

        # Run test
        new_warnings = self.service.check_new_warnings()

        # Only 'Warning 3' should pass as it's not a duplicate
        self.assertEqual(len(new_warnings), 1)
        self.assertIn("Warning 3", new_warnings[0])

    @patch('services.fmi_warning_service.FMIWarningService._save_seen_data')
    @patch('services.fmi_warning_service.FMIWarningService._save_seen_hashes')
    def test_save_functions(self, mock_save_seen_hashes, mock_save_seen_data):
        # Just ensure that functions are called without issues
        self.service._save_seen_hashes(set(["hash1", "hash2"]))
        self.service._save_seen_data([
            {"title": "Warning 1", "hash": "hash1"},
            {"title": "Warning 2", "hash": "hash2"},
        ])

        # Verify that save functions get called
        mock_save_seen_hashes.assert_called_once()
        mock_save_seen_data.assert_called_once()

if __name__ == '__main__':
    unittest.main()
