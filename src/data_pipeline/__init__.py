"""Initialization module for the data pipeline.

This module provides functions to create and configure the unified data pipeline.
"""

from src.core.config import AppSettings
from src.data_pipeline.pipeline import UnifiedDataPipeline


def create_data_pipeline(settings: AppSettings) -> UnifiedDataPipeline:
    """Create and configure a unified data pipeline."""
    return UnifiedDataPipeline(settings)
