import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = Field(default="TutorChat API")
    api_v1_prefix: str = Field(default="/api")

    # LLM / LLMProxy configuration
    llm_model: str = Field(default="4o-mini")
    llm_system_prompt: str = Field(
        default=(
            "You are a supportive  tutor. "
            "Ask clarifying questions, give concise explanations, and provide examples."
        )
    )

    LLMPROXY_API_KEY: str 
    LLMPROXY_ENDPOINT: str 
    

    # Optional: namespace for future RAG or multi-tenant setups
    default_session_prefix: str = Field(default="tutor-session-")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()

