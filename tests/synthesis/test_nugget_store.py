import unittest
from unittest.mock import MagicMock

from src.synthesis.nugget_store import NuggetStore


class TestNuggetStore(unittest.TestCase):
    def setUp(self):
        self.nugget_store = NuggetStore()

    def test_store_nuggets_happy_path(self):
        """
        Test the happy path for storing a batch of nuggets in ChromaDB.
        """
        # Arrange
        mock_collection = MagicMock()
        nuggets = [
            {
                "detailed_analysis": "analysis 1",
                "embedding": [0.1],
                "some_list": [1, 2],
                "none_value": None,
            }
        ]

        # Act
        num_stored = self.nugget_store.store_nuggets_batch(mock_collection, nuggets)

        # Assert
        self.assertEqual(num_stored, 1)
        mock_collection.add.assert_called_once()

        # Check that metadata was sanitized correctly
        call_args = mock_collection.add.call_args
        metadatas = call_args.kwargs["metadatas"]
        self.assertEqual(len(metadatas), 1)
        self.assertNotIn("embedding", metadatas[0])
        self.assertNotIn("none_value", metadatas[0])
        self.assertEqual(
            metadatas[0]["some_list"], "[1, 2]"
        )  # Check list serialization
