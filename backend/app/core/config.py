"""
Application configuration using pydantic-settings.
All settings are loaded from environment variables with fallback defaults.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Central configuration for the Adaptive Diagnostic Engine."""

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "adaptive_engine"

    # OpenAI
    openai_api_key: Optional[str] = None

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    # Adaptive Test Parameters
    max_questions_per_session: int = 10
    initial_ability: float = 0.5

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton instance
settings = Settings()
