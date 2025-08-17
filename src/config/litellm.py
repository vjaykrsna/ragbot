from dataclasses import dataclass


@dataclass
class LiteLLMSettings:
    """Settings for LiteLLM proxy and models."""

    proxy_url: str | None = None
    use_local_file_cache: bool = False
    proxy_api_key: str | None = None
    synthesis_model_name: str = "gemini-synthesis-model"
    embedding_model_name: str = "gemini-embedding-model"

    @property
    def synthesis_model_proxy(self) -> str:
        return f"litellm_proxy/{self.synthesis_model_name}"

    @property
    def embedding_model_proxy(self) -> str:
        return f"litellm_proxy/{self.embedding_model_name}"
