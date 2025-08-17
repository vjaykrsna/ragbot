"""
This package contains scripts for the application.

The main workflows are exposed here so they can be called from a unified CLI.
"""

from . import extract_history, process_data, synthesize_knowledge

__all__ = ["extract_history", "process_data", "synthesize_knowledge"]
