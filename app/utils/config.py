"""Application configuration settings using Pydantic."""

from functools import lru_cache
from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    """Application configuration settings."""

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000
    openai_temperature: float = 0.3

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # CORS Configuration
    allowed_origins: list[str] = ["*"]

    # Trusted Hosts Configuration
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "0.0.0.0"]

    # Rate Limiting
    rate_limit_per_minute: int = 30

    class Config:
        """Pydantic configuration to load from .env file."""
        env_file = ".env"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the application settings, loading them if necessary."""
    return Settings()
