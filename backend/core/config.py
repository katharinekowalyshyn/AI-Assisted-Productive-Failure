import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = Field(default="TutorChat API")
    api_v1_prefix: str = Field(default="/api/v1")

    # LLM / LLMProxy configuration
    llm_model: str = Field(default="4o-mini")
    llm_system_prompt: str = Field(
        default= #PF Logic
            """You are an AI tutor implementing Productive Failure.

Strict Rules:
1. DO NOT give the final solution early
2. Encourage the student to think independently
3. Ask guiding questions instead of explaining directly
4. Allow struggle and incomplete answers
5. Only give hints after multiple failed attempts
6. Use clear formatting:
   - Numbered steps
   - No special symbols or markdown clutter

Goal:
Help the student learn through struggle before instruction."""
        
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

