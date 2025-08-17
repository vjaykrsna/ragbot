from dataclasses import dataclass


@dataclass
class SynthesisSettings:
    """Settings for the knowledge synthesis process."""

    max_workers: int = 5
    requests_per_minute: int = 90
    batch_size: int = 2
