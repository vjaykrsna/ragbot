"""
Main orchestrator for the data processing pipeline.

This module provides a top-level class that wires together all the components
of the data processing pipeline, from data source to conversation building.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List

from src.core.config import AppSettings
from src.processing.anonymizer import Anonymizer
from src.processing.conversation_builder import ConversationBuilder
from src.processing.data_source import DataSource
from src.processing.external_sorter import ExternalSorter


class DataProcessingPipeline:
    """
    Orchestrates the entire data processing workflow.
    """

    def __init__(
        self,
        settings: AppSettings,
        data_source: DataSource,
        sorter: ExternalSorter,
        anonymizer: Anonymizer,
        conv_builder: ConversationBuilder,
    ):
        """
        Initializes the pipeline with its dependencies.
        """
        self.settings = settings
        self.data_source = data_source
        self.sorter = sorter
        self.anonymizer = anonymizer
        self.conv_builder = conv_builder
        self.logger = logging.getLogger(__name__)
        self.number_re = re.compile(
            r"(?P<number>\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\b)\s*(?P<unit>%|percent|rs|inr|₹|km|m|kg|k|lakh|crore|million|billion)?",
            re.IGNORECASE,
        )

    def run(self) -> None:
        """
        Executes the entire data processing pipeline.
        """
        self.logger.info("🚀 Starting Phase 2: Streaming Data Processing & KB Creation")

        # The main processing stream
        # The sorter now reads from the data_source (the database)
        sorted_stream = self.sorter.sort(self.data_source)
        processed_stream = (
            self._process_record(rec, self.anonymizer) for rec in sorted_stream
        )
        conversation_stream = self.conv_builder.process_stream(processed_stream)

        # Persistence
        output_file = os.path.join(
            self.settings.paths.processed_data_dir,
            self.settings.paths.processed_conversations_file,
        )
        os.makedirs(self.settings.paths.processed_data_dir, exist_ok=True)

        total_convs = self._write_conversations(conversation_stream, output_file)

        self.anonymizer.persist()

        self.logger.info(
            f"Stream processing complete: {total_convs:,} conversations written to {output_file}"
        )
        self.logger.info("✅ Data processing complete.")

    def _process_record(
        self, rec: Dict[str, Any], anonymizer: Anonymizer
    ) -> Dict[str, Any]:
        """Processes a single record: anonymization and normalization."""
        # Anonymize sender ID
        sender_id = rec.get("sender_id")
        if sender_id:
            rec["sender_id"] = anonymizer.anonymize(sender_id)

        # Lightweight numeric normalization
        content = rec.get("content", "")
        if isinstance(content, str):
            rec["normalized_values"] = self._normalize_numbers(content)
        else:
            rec["normalized_values"] = []

        return rec

    def _normalize_numbers(self, text: str) -> List[Dict[str, Any]]:
        """Extracts simple numeric facts from text."""
        results = []
        for m in self.number_re.finditer(text):
            num_str = m.group("number").replace(",", "")
            try:
                val = float(num_str)
            except ValueError:
                val = None
            results.append(
                {
                    "span": m.group(0),
                    "value": val,
                    "unit": (m.group("unit") or "").lower(),
                    "confidence": "medium" if val is not None else "low",
                }
            )
        return results

    def _write_conversations(self, conversation_stream, output_file: str) -> int:
        """Writes the stream of conversation envelopes to the final JSON file."""
        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("[\n")
            first = True
            for conv in conversation_stream:
                if not first:
                    f.write(",\n")
                json.dump(conv, f, ensure_ascii=False)
                first = False
                count += 1
            f.write("\n]\n")
        return count
