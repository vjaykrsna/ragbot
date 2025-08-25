"""Unified data pipeline for the application.

This module provides a standardized data flow from extraction to synthesis.
"""

import json
import os
from typing import Any, Dict, Generator

import structlog

from src.core.config import AppSettings
from src.core.database import Database
from src.processing.anonymizer import Anonymizer
from src.processing.conversation_builder import ConversationBuilder
from src.processing.data_source import DataSource
from src.processing.external_sorter import ExternalSorter

logger = structlog.get_logger(__name__)


class GeneratorDataSource(DataSource):
    """A DataSource that wraps a generator."""

    def __init__(self, generator: Generator[Dict[str, Any], None, None]):
        self.generator = generator

    def __iter__(self) -> Generator[Dict[str, Any], None, None]:
        """Iterate through the wrapped generator."""
        yield from self.generator


class DataPipelineStage:
    """Base class for data pipeline stages."""

    def process(self, data=None):
        """Process data and return the result."""
        raise NotImplementedError


class DataSourceStage(DataPipelineStage):
    """Stage for reading data from the database."""

    def __init__(self, db: Database):
        self.db = db

    def process(self, data=None) -> Generator[Dict[str, Any], None, None]:
        """Read messages from the database."""
        logger.info("Reading messages from the database.")
        yield from self.db.get_all_messages()


class SortingStage(DataPipelineStage):
    """Stage for sorting messages."""

    def __init__(self, sorter: ExternalSorter):
        self.sorter = sorter

    def process(self, data_stream=None):
        """Sort messages by date."""
        logger.info("Sorting messages by date.")
        # Wrap the generator in a DataSource-like object
        data_source = GeneratorDataSource(data_stream)
        yield from self.sorter.sort(data_source)


class AnonymizationStage(DataPipelineStage):
    """Stage for anonymizing messages."""

    def __init__(self, anonymizer: Anonymizer):
        self.anonymizer = anonymizer

    def process(self, data_stream=None):
        """Anonymize messages."""
        logger.info("Anonymizing messages.")
        yield from self.anonymizer.process_stream(data_stream)


class ConversationBuildingStage(DataPipelineStage):
    """Stage for building conversations from messages."""

    def __init__(self, conv_builder: ConversationBuilder):
        self.conv_builder = conv_builder

    def process(self, data_stream=None):
        """Group messages into conversations."""
        logger.info("Building conversations from messages.")
        yield from self.conv_builder.process_stream(data_stream)


class PersistenceStage(DataPipelineStage):
    """Stage for persisting processed data."""

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def process(self, data_stream=None):
        """Write conversations to the processed conversations file."""
        logger.info("Persisting processed conversations.")
        output_file = self.settings.paths.processed_conversations_file
        os.makedirs(self.settings.paths.processed_data_dir, exist_ok=True)

        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("[\n")
            first = True
            for conv in data_stream:
                if not first:
                    f.write(",\n")
                json.dump(conv, f, ensure_ascii=False)
                first = False
                count += 1
            f.write("\n]\n")

        logger.info(f"Wrote {count} conversations to {output_file}")
        return count


class UnifiedDataPipeline:
    """Unified data pipeline that orchestrates all stages of data processing."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.db = Database(settings.paths)
        self.anonymizer = Anonymizer(settings.paths)
        self.sorter = ExternalSorter()
        self.conv_builder = ConversationBuilder(settings.conversation)

        # Create pipeline stages
        self.stages = [
            DataSourceStage(self.db),
            SortingStage(self.sorter),
            AnonymizationStage(self.anonymizer),
            ConversationBuildingStage(self.conv_builder),
            PersistenceStage(settings),
        ]

    def run(self) -> int:
        """Run the entire data pipeline and return the number of processed conversations."""
        logger.info("🚀 Starting unified data processing pipeline")

        # Start with the first stage
        data = None

        # Process through each stage
        for i, stage in enumerate(self.stages):
            if i == len(self.stages) - 1:  # Last stage (persistence)
                data = stage.process(data)
            elif i == 0:  # First stage (data source)
                data = stage.process()
            else:  # Middle stages
                data = stage.process(data)

        logger.info("✅ Unified data processing pipeline complete")
        return (
            data if data is not None else 0
        )  # Return the count from the persistence stage
