import concurrent.futures
import hashlib
import logging
import threading
from collections import defaultdict
from typing import Any, Dict, List

import chromadb
from chromadb.api.models.Collection import Collection
from pyrate_limiter import Duration, Limiter, Rate
from tqdm import tqdm

from src.core.app import initialize_app
from src.core.config import AppSettings
from src.core.database import Database
from src.synthesis.conversation_optimizer import ConversationOptimizer
from src.synthesis.data_loader import DataLoader
from src.synthesis.failed_batch_handler import FailedBatchHandler
from src.synthesis.nugget_embedder import NuggetEmbedder
from src.synthesis.nugget_generator import NuggetGenerator
from src.synthesis.nugget_store import NuggetStore
from src.synthesis.progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

# Thread-safe locks
chroma_lock = threading.Lock()
fail_file_lock = threading.Lock()


class KnowledgeSynthesizer:
    """
    Orchestrates the entire knowledge base population process.
    """

    def __init__(
        self,
        settings: AppSettings,
        db: "Database",
        db_client: chromadb.Client,
        data_loader: DataLoader,
        nugget_generator: NuggetGenerator,
        nugget_embedder: NuggetEmbedder,
        nugget_store: NuggetStore,
        progress_tracker: ProgressTracker,
        failed_batch_handler: FailedBatchHandler,
    ):
        self.settings = settings
        self.db = db
        self.db_client = db_client
        self.data_loader = data_loader
        self.nugget_generator = nugget_generator
        self.nugget_embedder = nugget_embedder
        self.nugget_store = nugget_store
        self.progress_tracker = progress_tracker
        self.failed_batch_handler = failed_batch_handler
        self.rate = Rate(self.settings.synthesis.requests_per_minute, Duration.MINUTE)
        self.limiter = Limiter(self.rate, max_delay=60000)

    def run(self) -> None:
        """Executes the entire synthesis pipeline."""
        logger.info("🚀 Starting Knowledge Base v2 Synthesis")

        collection = self._setup_database()
        conversations = self.data_loader.load_processed_data()
        prompt_template = self.data_loader.load_prompt_template()
        if not conversations or not prompt_template:
            return

        self._synthesize_and_populate(conversations, prompt_template, collection)

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

    def _synthesize_and_populate(
        self,
        conversations: List[Dict[str, Any]],
        prompt_template: str,
        collection: Collection,
    ) -> None:
        """Processes all conversations in batches and populates the database."""
        last_processed_index = self.progress_tracker.load_progress()
        start_index = last_processed_index + 1

        if start_index >= len(conversations):
            logger.info("All conversations have already been processed.")
            return

        logger.info(f"Resuming from conversation index {start_index}")

        # Apply conversation optimization before batching
        logger.info("Applying conversation optimization...")
        optimized_conversations = self.nugget_generator.optimizer.optimize_batch(
            conversations[start_index:]
        )
        logger.info(
            f"Optimization complete: {len(optimized_conversations)} high-quality conversations ready for processing"
        )

        batch_size = self.settings.synthesis.batch_size
        batches = [
            optimized_conversations[i : i + batch_size]
            for i in range(0, len(optimized_conversations), batch_size)
        ]

        processed_hashes = self.progress_tracker.load_processed_hashes()
        total_nuggets_stored = 0

        with tqdm(total=len(batches), desc="Synthesizing Knowledge") as pbar:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.settings.synthesis.max_workers
            ) as executor:
                future_to_batch_index = {}
                batch_index_to_hash = {}
                for i, batch in enumerate(batches):
                    bh = self._batch_hash(batch)
                    batch_index_to_hash[i] = bh
                    if bh in processed_hashes:
                        logger.info(f"Skipping already-processed batch {i} (hash={bh})")
                        pbar.update(1)
                        continue
                    fut = executor.submit(
                        self._process_conversation_batch,
                        batch,
                        prompt_template,
                        collection,
                    )
                    future_to_batch_index[fut] = i

                for future in concurrent.futures.as_completed(future_to_batch_index):
                    batch_index = future_to_batch_index[future]
                    try:
                        num_stored = future.result()
                        if num_stored > 0:
                            bh = batch_index_to_hash.get(batch_index)
                            if bh:
                                processed_hashes.add(bh)
                            total_nuggets_stored += num_stored
                            last_item_in_batch = len(batches[batch_index]) - 1
                            # Since we're working with optimized conversations, adjust the index calculation
                            new_last_processed_index = (
                                start_index
                                + batch_index * batch_size
                                + last_item_in_batch
                            )
                            self.progress_tracker.save_progress(
                                new_last_processed_index
                            )
                    except Exception as e:
                        logger.error(
                            f"An error occurred while processing batch index {batch_index}: {e}",
                            exc_info=True,
                        )
                    pbar.update(1)
                    pbar.set_postfix({"Stored": f"{total_nuggets_stored}"})

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

    data_loader = DataLoader(settings)
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
    )
    synthesizer.run()


if __name__ == "__main__":
    main()
