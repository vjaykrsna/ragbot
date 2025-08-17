import os
import tempfile
import unittest

from src.core.config import PathSettings
from src.processing.anonymizer import Anonymizer


class TestAnonymizer(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory for test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_path_settings = PathSettings()
        self.mock_path_settings.user_map_file = os.path.join(
            self.temp_dir.name, "user_map.json"
        )

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_anonymize_new_and_existing_users(self):
        """Test that new users get sequential IDs and existing users get the same ID."""
        anonymizer = Anonymizer(self.mock_path_settings)
        self.assertEqual(anonymizer.anonymize("user_a"), "User_1")
        self.assertEqual(anonymizer.anonymize("user_b"), "User_2")
        self.assertEqual(anonymizer.anonymize("user_a"), "User_1")
        self.assertEqual(anonymizer.anonymize("12345"), "User_3")

    def test_persist_and_load_user_map(self):
        """Test that the user map is correctly saved to and loaded from a file."""
        # First instance
        anonymizer1 = Anonymizer(self.mock_path_settings)
        anonymizer1.anonymize("user_a")
        anonymizer1.anonymize("user_b")
        anonymizer1.persist()

        # Second instance, should load the map from the first
        anonymizer2 = Anonymizer(self.mock_path_settings)
        self.assertEqual(anonymizer2.anonymize("user_a"), "User_1")
        self.assertEqual(anonymizer2.anonymize("user_b"), "User_2")
        self.assertEqual(anonymizer2.anonymize("user_c"), "User_3")

    def test_load_corrupted_user_map(self):
        """Test that the anonymizer starts fresh if the user map is corrupted."""
        # Create a corrupted user map file
        with open(self.mock_path_settings.user_map_file, "w") as f:
            f.write("this is not json")

        anonymizer = Anonymizer(self.mock_path_settings)
        self.assertEqual(anonymizer.user_map, {})
        self.assertEqual(anonymizer.next_user_num, 1)
        self.assertEqual(anonymizer.anonymize("user_a"), "User_1")
