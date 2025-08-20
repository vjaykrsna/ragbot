import unittest
from unittest.mock import MagicMock, patch

from src.scripts.synthesize_knowledge import KnowledgeSynthesizer, main


class TestKnowledgeSynthesizer(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_db = MagicMock()
        self.mock_db_client = MagicMock()
        self.mock_data_loader = MagicMock()
        self.mock_nugget_generator = MagicMock()
        self.mock_nugget_embedder = MagicMock()
        self.mock_nugget_store = MagicMock()
        self.mock_progress_tracker = MagicMock()
        self.mock_failed_batch_handler = MagicMock()

        self.synthesizer = KnowledgeSynthesizer(
            self.mock_settings,
            self.mock_db,
            self.mock_db_client,
            self.mock_data_loader,
            self.mock_nugget_generator,
            self.mock_nugget_embedder,
            self.mock_nugget_store,
            self.mock_progress_tracker,
            self.mock_failed_batch_handler,
        )

    @patch("src.scripts.synthesize_knowledge.KnowledgeSynthesizer._setup_database")
    @patch(
        "src.scripts.synthesize_knowledge.KnowledgeSynthesizer._synthesize_and_populate"
    )
    def test_run(self, mock_populate, mock_setup_db):
        """Test the main run method of the synthesizer."""
        # Arrange
        mock_setup_db.return_value = "mock_collection"
        self.mock_data_loader.load_processed_data.return_value = ["mock_conversation"]
        self.mock_data_loader.load_prompt_template.return_value = "mock_prompt"

        # Act
        self.synthesizer.run()

        # Assert
        mock_setup_db.assert_called_once()
        self.mock_data_loader.load_processed_data.assert_called_once()
        self.mock_data_loader.load_prompt_template.assert_called_once()
        mock_populate.assert_called_once_with(
            ["mock_conversation"], "mock_prompt", "mock_collection"
        )

    def test_setup_database(self):
        """Test the database setup method."""
        # Arrange
        mock_collection = MagicMock()
        self.mock_db_client.get_or_create_collection.return_value = mock_collection

        # Act
        collection = self.synthesizer._setup_database()

        # Assert
        self.mock_db_client.get_or_create_collection.assert_called_once_with(
            name=self.mock_settings.rag.collection_name
        )
        self.assertEqual(collection, mock_collection)

    @patch(
        "src.scripts.synthesize_knowledge.KnowledgeSynthesizer._process_conversation_batch"
    )
    def test_synthesize_and_populate(self, mock_process_batch):
        """Test the synthesis and population process."""
        # Arrange
        self.mock_settings.synthesis.max_workers = 1
        self.mock_progress_tracker.load_progress.return_value = -1
        self.mock_progress_tracker.load_processed_hashes.return_value = set()
        mock_process_batch.return_value = 1
        # Mock the optimizer to return the same conversations (bypass filtering)
        self.mock_nugget_generator.optimizer.optimize_batch.return_value = [
            {
                "id": 1,
                "messages": [
                    {"content": "test message 1"},
                    {"content": "test message 2"},
                ],
            },
            {
                "id": 2,
                "messages": [
                    {"content": "test message 3"},
                    {"content": "test message 4"},
                ],
            },
        ]

        conversations = [{"id": 1}, {"id": 2}]
        prompt = "prompt"
        collection = "collection"

        # Act
        self.synthesizer._synthesize_and_populate(conversations, prompt, collection)

        # Assert
        self.assertEqual(mock_process_batch.call_count, 2)
        self.mock_progress_tracker.save_progress.assert_called()
        self.mock_progress_tracker.save_processed_hashes.assert_called()

    @patch(
        "src.scripts.synthesize_knowledge.KnowledgeSynthesizer._run_numeric_verifier"
    )
    def test_process_conversation_batch(self, mock_run_verifier):
        """Test the processing of a single batch of conversations."""
        # Arrange
        self.mock_nugget_generator.generate_nuggets_batch.return_value = ["nugget1"]
        self.mock_nugget_embedder.embed_nuggets_batch.return_value = [
            "nugget_with_embedding"
        ]
        mock_run_verifier.return_value = ["verified_nugget"]
        self.mock_nugget_store.store_nuggets_batch.return_value = 1

        batch = ["conversation"]
        prompt = "prompt"
        collection = "collection"

        # Act
        result = self.synthesizer._process_conversation_batch(batch, prompt, collection)

        # Assert
        self.assertEqual(result, 1)
        self.mock_nugget_generator.generate_nuggets_batch.assert_called_once_with(
            batch, prompt
        )
        self.mock_nugget_embedder.embed_nuggets_batch.assert_called_once_with(
            ["nugget1"]
        )
        mock_run_verifier.assert_called_once_with(["nugget_with_embedding"], batch)
        self.mock_nugget_store.store_nuggets_batch.assert_called_once_with(
            collection, ["verified_nugget"]
        )

    def test_run_numeric_verifier(self):
        """Test the numeric verifier."""
        # Arrange
        nuggets = [
            {"normalized_values": [{"value": 100}]},
            {"normalized_values": [{"value": 200}]},
            {"normalized_values": [{"value": 300}]},
        ]
        conversations = [
            {
                "messages": [
                    {"normalized_values": [{"value": 100}]},
                    {"normalized_values": [{"value": 300}]},
                ]
            }
        ]

        # Act
        result = self.synthesizer._run_numeric_verifier(nuggets, conversations)

        # Assert
        self.assertFalse(result[0]["verification_numeric_mismatch"])
        self.assertTrue(result[1]["verification_numeric_mismatch"])
        self.assertFalse(result[2]["verification_numeric_mismatch"])

    def test_batch_hash(self):
        """Test the batch hashing function."""
        batch = [{"ingestion_hash": "hash1"}, {"ingestion_hash": "hash2"}]
        h = self.synthesizer._batch_hash(batch)
        self.assertIsInstance(h, str)
        self.assertGreater(len(h), 0)


@patch("src.scripts.synthesize_knowledge.initialize_app")
@patch("src.scripts.synthesize_knowledge.KnowledgeSynthesizer")
@patch("src.scripts.synthesize_knowledge.DataLoader")
@patch("src.scripts.synthesize_knowledge.Limiter")
@patch("src.scripts.synthesize_knowledge.NuggetGenerator")
@patch("src.scripts.synthesize_knowledge.NuggetEmbedder")
@patch("src.scripts.synthesize_knowledge.NuggetStore")
@patch("src.scripts.synthesize_knowledge.ProgressTracker")
@patch("src.scripts.synthesize_knowledge.FailedBatchHandler")
def test_main(
    mock_failed_batch_handler,
    mock_progress_tracker,
    mock_nugget_store,
    mock_nugget_embedder,
    mock_nugget_generator,
    mock_limiter,
    mock_data_loader,
    mock_synthesizer,
    mock_initialize_app,
):
    """Test the main function."""
    # Arrange
    mock_context = MagicMock()
    mock_initialize_app.return_value = mock_context
    mock_synthesizer_instance = MagicMock()
    mock_synthesizer.return_value = mock_synthesizer_instance

    # Act
    main()

    # Assert
    mock_initialize_app.assert_called_once()
    mock_synthesizer.assert_called_once()
    mock_synthesizer_instance.run.assert_called_once()
