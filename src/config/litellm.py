from pydantic import BaseModel, Field


class LiteLLMSettings(BaseModel):
    """Settings for LiteLLM proxy and models."""

    proxy_url: str | None = Field(None, env="LITELLM_PROXY_URL")
    use_local_file_cache: bool = Field(False, env="USE_LOCAL_FILE_CACHE")
    proxy_api_key: str | None = Field(None, env="LITELLM_PROXY_API_KEY")
    synthesis_model_name: str = "gemini-synthesis-model"
    embedding_model_name: str = "gemini-embedding-model"

    @property
    def synthesis_model_proxy(self) -> str:
        return f"litellm_proxy/{self.synthesis_model_name}"

    @property
    def embedding_model_proxy(self) -> str:
        return f"litellm_proxy/{self.embedding_model_name}"
