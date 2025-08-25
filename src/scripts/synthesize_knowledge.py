import concurrent.futures
import hashlib
import json
import threading
from collections import defaultdict
from typing import Any, Dict, List, Set

import structlog
from chromadb.api.models.Collection import Collection
from pyrate_limiter import Duration, Limiter, Rate

from src.core.app import initialize_app
from src.core.config import AppSettings
from src.core.database import Database
from src.core.error_handler import AlertManager, CheckpointManager
from src.rag.rag_pipeline import LiteLLMEmbeddingFunction
from src.synthesis.conversation_optimizer import ConversationOptimizer
from src.synthesis.data_loader import DataLoader
from src.synthesis.failed_batch_handler import FailedBatchHandler
from src.synthesis.nugget_embedder import NuggetEmbedder
from src.synthesis.nugget_generator import NuggetGenerator
from src.synthesis.nugget_store import NuggetStore
from src.synthesis.progress_tracker import ProgressTracker

logger = structlog.get_logger(__name__)


class KnowledgeSynthesizer:
    """
    Orchestrates the entire knowledge base population process.
    """

    def __init__(
        self,
        settings: AppSettings,
        db: Database,
        db_client,
        data_loader: DataLoader,
        nugget_generator: NuggetGenerator,
        nugget_embedder: NuggetEmbedder,
        nugget_store: NuggetStore,
        progress_tracker: ProgressTracker,
        failed_batch_handler: FailedBatchHandler,
        conversation_optimizer: ConversationOptimizer,
    ):
        """
        Initializes the KnowledgeSynthesizer.

        Args:
            settings: The application settings.
            db: The database instance.
            db_client: The database client.
            data_loader: The data loader instance.
            nugget_generator: The nugget generator instance.
            nugget_embedder: The nugget embedder instance.
            nugget_store: The nugget store instance.
            progress_tracker: The progress tracker instance.
            failed_batch_handler: The failed batch handler instance.
            conversation_optimizer: The conversation optimizer instance.
        """
        self.settings = settings
        self.db = db
        self.db_client = db_client
        self.data_loader = data_loader
        self.nugget_generator = nugget_generator
        self.nugget_embedder = nugget_embedder
        self.nugget_store = nugget_store
        self.progress_tracker = progress_tracker
        self.failed_batch_handler = failed_batch_handler
        self.conversation_optimizer = conversation_optimizer

        # Initialize error handling components
        self.checkpoint_manager = CheckpointManager(
            settings.paths.synthesis_checkpoint_file
        )
        self.alert_manager = AlertManager()

        # Rate limiting for API calls
        self.limiter = Limiter(
            Rate(settings.synthesis.requests_per_minute, Duration.MINUTE)
        )

    def _get_or_create_collection(self, collection_name: str):
        """Get or create a collection in the database."""
        embedding_function = LiteLLMEmbeddingFunction(
            model_name=self.settings.litellm.embedding_model_name or ""
        )
        return self.db_client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
        )

    def run(self) -> None:
        """Executes the entire synthesis pipeline."""
        logger.info("🚀 Starting Knowledge Base v2 Synthesis")

        collection = self._setup_database()
        conversations = self.data_loader.load_processed_data()
        prompt_template = self.data_loader.load_prompt_template()
        if not conversations or not prompt_template:
            return

        # Convert to the format expected by _synthesize_and_populate
        self._synthesize_and_populate(conversations, prompt_template, collection)

        logger.info("✅ Knowledge base synthesis complete.")

    def _synthesize_and_populate(
        self,
        conversations: List[Dict[str, Any]],
        prompt_template: str,
        collection: Collection,
    ) -> None:
        """
        Internal method to synthesize and populate knowledge base.

        Args:
            conversations: List of conversations to process
            prompt_template: The prompt template for nugget generation
            collection: The ChromaDB collection to store nuggets
        """
        logger.info(f"Loaded {len(conversations)} conversations from database.")

        if not conversations:
            logger.info("No conversations found. Nothing to process.")
            return

        # Apply conversation optimization
        logger.info("Applying conversation optimization...")
        optimized_conversations = self.conversation_optimizer.optimize_conversations(
            conversations
        )
        logger.info(
            f"Optimization complete. Reduced from {len(conversations)} to {len(optimized_conversations)} conversations."
        )

        # Load checkpoint if available
        checkpoint_data = self.checkpoint_manager.load_checkpoint()
        start_index = checkpoint_data.get("last_processed_index", 0)
        processed_hashes = set(checkpoint_data.get("processed_hashes", []))

        # If no checkpoint, load from progress tracker
        if start_index == 0:
            start_index = self.progress_tracker.load_progress() + 1
        if not processed_hashes:
            processed_hashes = self.progress_tracker.load_processed_hashes()

        # If we're resuming from a checkpoint, adjust our conversation list
        if start_index > 0:
            logger.info(f"Resuming from conversation index {start_index}")
            if start_index < len(optimized_conversations):
                optimized_conversations = optimized_conversations[start_index:]
            else:
                logger.info("All conversations have already been processed.")
                return

        # Process conversations in batches
        batch_size = self.settings.synthesis.batch_size
        batches = [
            optimized_conversations[i : i + batch_size]
            for i in range(0, len(optimized_conversations), batch_size)
        ]

        if not batches:
            logger.info("No batches to process.")
            return

        logger.info(
            f"Processing {len(batches)} batches of {batch_size} conversations each."
        )

        # Process batches with checkpointing
        self._process_batches_with_checkpointing(
            batches,
            prompt_template,
            collection,
            start_index,
            processed_hashes,
            batch_size,
        )

        # Clear checkpoint on successful completion
        self.checkpoint_manager.clear_checkpoint()

        logger.info("✅ Knowledge base synthesis complete.")

    def _setup_database(self) -> Collection:
        """Initializes or connects to the vector database and collection."""
        collection_name = self.settings.rag.collection_name
        logger.info(f"Attempting to get or create collection: '{collection_name}'")
        collection = self.db_client.get_or_create_collection(name=collection_name)

        try:
            self.db_client.get_collection(name=collection_name)
            logger.info(f"Successfully verified collection '{collection_name}'.")
        except Exception as e:
            logger.error(f"Failed to verify collection '{collection_name}': {e}")
            raise

        logger.info(
            f"Database collection '{collection_name}' is ready with {collection.count()} items."
        )
        return collection

    def _process_batches_with_checkpointing(
        self,
        batches: List[List[Dict[str, Any]]],
        prompt_template: str,
        collection: Collection,
        start_index: int,
        processed_hashes: Set[str],
        batch_size: int,
    ) -> None:
        """
        Process conversation batches with checkpoint-based recovery.

        Args:
            batches: List of conversation batches to process.
            prompt_template: The prompt template for nugget generation.
            collection: The ChromaDB collection to store nuggets.
            start_index: The starting index for processing.
            processed_hashes: Set of already processed batch hashes.
            batch_size: The size of each batch.
        """
        total_batches = len(batches)
        completed_batches = 0
        total_nuggets_stored = 0
        batch_index_to_hash = {}

        # Create a hash for each batch to track progress
        for i, batch in enumerate(batches):
            batch_content = json.dumps(batch, sort_keys=True)
            batch_hash = hashlib.md5(batch_content.encode()).hexdigest()
            batch_index_to_hash[i] = batch_hash

        # Thread-safe locks for shared resources
        stats_lock = threading.Lock()
        hashes_lock = threading.Lock()
        progress_lock = threading.Lock()

        logger.info(
            f"Starting batch processing: {total_batches} batches, {batch_size} items each"
        )

        # Process batches with thread pool
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.settings.synthesis.max_workers
        ) as executor:
            future_to_batch_index = {}

            # Submit all batches to the executor
            for i, batch in enumerate(batches):
                # Check if batch has already been processed
                bh = batch_index_to_hash.get(i)
                if bh and bh in processed_hashes:
                    logger.info(
                        f"Skipping already-processed batch {i + 1}/{total_batches} (hash={bh})"
                    )
                    completed_batches += 1
                    continue

                fut = executor.submit(
                    self._process_conversation_batch,
                    batch,
                    prompt_template,
                    collection,
                )
                future_to_batch_index[fut] = i

            # Process completed futures
            for future in concurrent.futures.as_completed(future_to_batch_index):
                batch_index = future_to_batch_index[future]
                try:
                    num_stored = future.result()
                    if num_stored > 0:
                        bh = batch_index_to_hash.get(batch_index)
                        if bh:
                            with hashes_lock:
                                processed_hashes.add(bh)
                        with stats_lock:
                            total_nuggets_stored += num_stored
                        last_item_in_batch = len(batches[batch_index]) - 1
                        # Calculate the actual index in the original conversation list
                        new_last_processed_index = (
                            start_index + batch_index * batch_size + last_item_in_batch
                        )

                        # Save checkpoint
                        with progress_lock:
                            self.checkpoint_manager.save_checkpoint(
                                last_processed_index=new_last_processed_index,
                                processed_hashes=list(processed_hashes),
                                total_nuggets_stored=total_nuggets_stored,
                                completed_batches=completed_batches + 1,
                                total_batches=total_batches,
                            )

                            # Also save to progress tracker for backward compatibility
                            self.progress_tracker.save_progress(
                                new_last_processed_index
                            )
                except Exception as e:
                    logger.error(
                        f"An error occurred while processing batch index {batch_index}: {e}",
                        exc_info=True,
                    )
                    # Send alert for critical failures
                    self.alert_manager.send_alert(
                        f"Critical error processing batch {batch_index}", exception=e
                    )

                with stats_lock:
                    completed_batches += 1
                logger.info(
                    f"Progress: {completed_batches}/{total_batches} batches completed (Total nuggets stored: {total_nuggets_stored})"
                )

        # Save final processed hashes
        with hashes_lock:
            self.progress_tracker.save_processed_hashes(processed_hashes)

        logger.info(
            f"\n--- Knowledge Synthesis Complete ---\n"
            f"Total nuggets stored in this run: {total_nuggets_stored}"
        )

    def _process_conversation_batch(
        self, batch: List[Dict[str, Any]], prompt_template: str, collection: Collection
    ) -> int:
        """Worker function to process a batch of conversations."""
        nuggets = self.nugget_generator.generate_nuggets_batch(batch, prompt_template)
        if not nuggets:
            return 0

        nuggets_with_embeddings = self.nugget_embedder.embed_nuggets_batch(nuggets)
        if not nuggets_with_embeddings:
            return 0

        verified = self._run_numeric_verifier(nuggets_with_embeddings, batch)
        num_stored = self.nugget_store.store_nuggets_batch(collection, verified)
        return num_stored

    def _run_numeric_verifier(
        self, nuggets: List[Dict[str, Any]], conversations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        source_numbers = defaultdict(list)
        for conv in conversations:
            conv_msgs = conv.get("conversation") or conv.get("messages") or []
            for m in conv_msgs:
                nvals = m.get("normalized_values") or []
                for nv in nvals:
                    if nv.get("value") is not None:
                        source_numbers[round(float(nv.get("value")), 6)].append(nv)

        for nug in nuggets:
            mismatches = []
            for nv in nug.get("normalized_values", []):
                val = nv.get("value")
                if val is None:
                    mismatches.append(nv)
                    continue
                key = round(float(val), 6)
                if key not in source_numbers:
                    mismatches.append(nv)

            if mismatches:
                nug["verification_numeric_mismatch"] = True
                nug["verification_mismatch_count"] = len(mismatches)
                nug["confidence"] = "Low"
            else:
                nug["verification_numeric_mismatch"] = False
                nug["confidence"] = "High"

        return nuggets

    def _batch_hash(self, batch: List[Dict[str, Any]]) -> str:
        parts = []
        for conv in batch:
            ih = conv.get("ingestion_hash")
            if not ih:
                msgs = conv.get("conversation") or conv.get("messages") or []
                joined = "".join(m.get("content", "") for m in msgs)
                ih = hashlib.md5(joined.encode("utf-8")).hexdigest()
            parts.append(ih)
        return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def main() -> None:
    """Initializes the application and runs the knowledge synthesis pipeline."""
    app_context = initialize_app()
    settings = app_context.settings
    db = app_context.db
    db_client = app_context.db_client

    data_loader = DataLoader(settings, db)
    limiter = Limiter(Rate(settings.synthesis.requests_per_minute, Duration.MINUTE))

    # Initialize optimization components
    optimizer = ConversationOptimizer()
    nugget_generator = NuggetGenerator(settings, limiter, optimizer)
    nugget_embedder = NuggetEmbedder(settings, limiter)
    nugget_store = NuggetStore()
    progress_tracker = ProgressTracker(settings)
    failed_batch_handler = FailedBatchHandler(settings)

    synthesizer = KnowledgeSynthesizer(
        settings,
        db,
        db_client,
        data_loader,
        nugget_generator,
        nugget_embedder,
        nugget_store,
        progress_tracker,
        failed_batch_handler,
        optimizer,  # conversation_optimizer
    )
    synthesizer.run()


if __name__ == "__main__":
    main()
