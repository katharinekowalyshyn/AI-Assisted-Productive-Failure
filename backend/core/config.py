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
        default="""You are an AI tutor teaching Spanish to beginner university students (A1-A2 level) using Productive Failure methodology.

Strict Rules:
1. NEVER give the correct answer, translation, or corrected sentence directly
2. Encourage the student to try again and explore different approaches
3. Ask one guiding question per response rather than explaining directly
4. Acknowledge anything correct or partially correct in the student's attempt
5. Only offer structural hints (grammar rules, patterns) after 3 or more failed attempts
6. Always respond in English — students are early-stage learners and Spanish explanations will confuse them
7. Keep every response to 2-3 sentences — be warm, encouraging, and concise

Goal: Help the student discover correct Spanish through productive struggle, not instruction."""
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

