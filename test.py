print("--- Script starting ---")
import os
import sys
import logging
import json

# Add src to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from utils import config
from utils.logger import setup_logging

def test_config_loading():
    """Tests if the configuration is loaded correctly."""
    print("--- Running Test: Configuration Loading ---")
    try:
        # Configuration is loaded at the module level, so we just check the variables
        assert config.TELEGRAM_BOT_TOKEN is not None, "TELEGRAM_BOT_TOKEN is not set"
        assert config.LITELLM_PROXY_URL is not None, "LITELLM_PROXY_URL is not set"
        assert config.DB_PATH is not None, "DB_PATH is not set"
        logging.info("✅ Configuration variables appear to be loaded.")
        logging.info(f"LiteLLM Proxy URL: {config.LITELLM_PROXY_URL}")
        logging.info(f"Database Path: {config.DB_PATH}")
    except Exception as e:
        logging.error(f"❌ An error occurred during configuration loading: {e}", exc_info=True)
    print("--- Test Finished: Configuration Loading ---\n")


from utils.litellm_client import embed

def test_litellm_connection():
    """Tests the connection to the LiteLLM proxy."""
    print("--- Running Test: LiteLLM Connection ---")
    try:
        config.initialize_litellm_client_stub()
        logging.info("✅ LiteLLM client initialized.")
        
        # Test the embedding function
        test_text = ["hello world"]
        embeddings = embed(test_text)
        
        if embeddings and isinstance(embeddings, list) and len(embeddings) > 0:
            logging.info(f"✅ Successfully received embeddings for: '{test_text[0]}'")
            assert isinstance(embeddings[0], list) and len(embeddings[0]) > 0, "Embedding vector is empty"
            logging.info("✅ Embedding format is correct.")
        else:
            logging.error("❌ Failed to get embeddings.")
    except Exception as e:
        logging.error(f"❌ An error occurred during LiteLLM connection test: {e}", exc_info=True)
    print("--- Test Finished: LiteLLM Connection ---\n")


def test_rag_pipeline():
    """Tests the full RAG pipeline."""
    from src.core.rag_pipeline import RAGPipeline
    print("--- Running Test: RAG Pipeline ---")
    try:
        # Explicitly delete the collection to ensure a clean slate
        import chromadb
        client = chromadb.PersistentClient(path=config.DB_PATH)
        client.delete_collection(name=config.COLLECTION_NAME)
        logging.info("✅ Deleted existing ChromaDB collection.")

        pipeline = RAGPipeline()
        logging.info("✅ RAG pipeline initialized.")

        # Check if the collection is empty and add a dummy document if it is
        if pipeline.collection.count() == 0:
            logging.warning("⚠️ ChromaDB collection is empty. Adding a dummy document for testing.")
            pipeline.collection.add(
                ids=["test_id_1"],
                documents=["This is a test document about project architecture."],
                metadatas=[{"full_text": "This is a test document about project architecture.", "status": "FACT"}]
            )
            logging.info("✅ Dummy document added.")

        # Test the query function
        test_query = "What is the project architecture?"
        response = pipeline.query(test_query)

        if response and "couldn't find any relevant information" not in response:
            logging.info(f"✅ Successfully received a response for the query: '{test_query}'")
            logging.info(f"Response: {response}")
        else:
            logging.error("❌ Failed to get a valid response from the RAG pipeline.")
    except Exception as e:
        logging.error(f"❌ An error occurred during the RAG pipeline test: {e}", exc_info=True)
    print("--- Test Finished: RAG Pipeline ---\n")


from src.scripts import process_data

def test_data_processing():
    """Tests the data processing script."""
    print("--- Running Test: Data Processing ---")
    try:
        # Create a dummy raw data file in a temporary directory
        raw_dir = config.RAW_DATA_DIR
        backup_dir = os.path.join(config.DATA_DIR, "raw_backup")
        if os.path.exists(raw_dir):
            os.rename(raw_dir, backup_dir)
        os.makedirs(raw_dir, exist_ok=True)
        
        dummy_data_path = os.path.join(raw_dir, "test_data.jsonl")
        with open(dummy_data_path, "w") as f:
            f.write('{"id": 1, "date": "2025-01-01T12:00:00Z", "sender_id": "user1", "content": "Hello"}\n')
            f.write('{"id": 2, "date": "2025-01-01T12:01:00Z", "sender_id": "user2", "content": "Hi there"}\n')
            f.write('{"id": 3, "date": "2025-01-01T13:00:00Z", "sender_id": "user1", "content": "This is a new conversation"}\n')
        logging.info(f"✅ Created dummy data file at {dummy_data_path}")

        # Run the data processing script
        process_data.main()

        # Check if the processed file was created
        processed_file = config.PROCESSED_CONVERSATIONS_FILE
        processed_path = os.path.join(config.PROCESSED_DATA_DIR, processed_file)
        assert os.path.exists(processed_path), f"Processed file not found at {processed_path}"
        logging.info(f"✅ Processed file created at {processed_path}")

        # Verify the contents of the processed file
        with open(processed_path, "r") as f:
            processed_conversations = json.load(f)
        assert len(processed_conversations) == 2, f"Expected 2 conversations, but found {len(processed_conversations)}"
        logging.info("✅ Processed file contains the correct number of conversations.")

    except Exception as e:
        logging.error(f"❌ An error occurred during the data processing test: {e}", exc_info=True)
    finally:
        # Clean up and restore the original raw data
        if os.path.exists(raw_dir):
            import shutil
            shutil.rmtree(raw_dir)
        if os.path.exists(backup_dir):
            os.rename(backup_dir, raw_dir)
        
        processed_path = os.path.join(config.PROCESSED_DATA_DIR, config.PROCESSED_CONVERSATIONS_FILE)
        if os.path.exists(processed_path):
            os.remove(processed_path)
        user_map_path = os.path.join(config.PROCESSED_DATA_DIR, config.USER_MAP_FILE)
        if os.path.exists(user_map_path):
            os.remove(user_map_path)

    print("--- Test Finished: Data Processing ---\n")


def main():
    """Main function to run all tests."""
    setup_logging()
    logging.info("🚀 Starting diagnostic tests...")
    
    test_config_loading()
    test_litellm_connection()
    test_rag_pipeline()
    test_data_processing()

    logging.info("🏁 Diagnostic tests finished.")

if __name__ == "__main__":
    main()
