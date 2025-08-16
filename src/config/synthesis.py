from pydantic import BaseModel, Field


class SynthesisSettings(BaseModel):
    """Settings for the knowledge synthesis process."""

    max_workers: int = Field(5, env="MAX_WORKERS")
    requests_per_minute: int = Field(90, env="REQUESTS_PER_MINUTE")
    batch_size: int = Field(2, env="BATCH_SIZE")
