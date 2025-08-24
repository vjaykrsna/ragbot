import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Metrics:
    """Simple metrics collection for tracking processing performance."""

    # Processing rates
    messages_processed: int = 0
    conversations_processed: int = 0
    nuggets_generated: int = 0

    # Timing
    start_time: float = field(default_factory=time.time)
    last_report_time: float = field(default_factory=time.time)

    # Errors
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # API calls
    api_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    api_errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_messages(self, count: int = 1):
        """Record processed messages."""
        self.messages_processed += count

    def record_conversations(self, count: int = 1):
        """Record processed conversations."""
        self.conversations_processed += count

    def record_nuggets(self, count: int = 1):
        """Record generated nuggets."""
        self.nuggets_generated += count

    def record_error(self, error_type: str):
        """Record an error."""
        self.error_counts[error_type] += 1

    def record_api_call(self, api_name: str, success: bool = True):
        """Record an API call."""
        self.api_calls[api_name] += 1
        if not success:
            self.api_errors[api_name] += 1

    def get_processing_rate(self, interval: Optional[float] = None) -> Dict[str, float]:
        """Get processing rates per second."""
        if interval is None:
            interval = time.time() - self.start_time
            if interval == 0:
                return {"messages_per_second": 0, "conversations_per_second": 0}

        return {
            "messages_per_second": self.messages_processed / interval
            if interval > 0
            else 0,
            "conversations_per_second": self.conversations_processed / interval
            if interval > 0
            else 0,
        }

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            from src.history_extractor.memory_utils import get_memory_usage_mb

            return get_memory_usage_mb()
        except Exception:
            return 0.0

    def report(self) -> Dict[str, Any]:
        """Generate a metrics report."""
        interval = time.time() - self.last_report_time
        rates = self.get_processing_rate(interval)

        report = {
            "timestamp": time.time(),
            "messages_processed": self.messages_processed,
            "conversations_processed": self.conversations_processed,
            "nuggets_generated": self.nuggets_generated,
            "processing_rates": rates,
            "memory_usage_mb": self.get_memory_usage_mb(),
            "error_counts": dict(self.error_counts),
            "api_calls": dict(self.api_calls),
            "api_errors": dict(self.api_errors),
        }

        self.last_report_time = time.time()
        return report

    def log_summary(self):
        """Log a summary of metrics."""
        report = self.report()
        rates = report["processing_rates"]

        logger.info(
            f"Metrics Summary: "
            f"Messages: {self.messages_processed}, "
            f"Conversations: {self.conversations_processed}, "
            f"Nuggets: {self.nuggets_generated}, "
            f"Rate: {rates['messages_per_second']:.1f} msgs/sec, "
            f"Memory: {report['memory_usage_mb']:.1f} MB"
        )

        # Log errors if any
        if self.error_counts:
            for error_type, count in self.error_counts.items():
                logger.warning(f"Error '{error_type}': {count} occurrences")

        # Log API issues if any
        for api_name, error_count in self.api_errors.items():
            total_calls = self.api_calls.get(api_name, 0)
            if total_calls > 0:
                error_rate = error_count / total_calls * 100
                logger.warning(
                    f"API '{api_name}': {error_count}/{total_calls} errors ({error_rate:.1f}%)"
                )
