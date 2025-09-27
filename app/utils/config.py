"""Application configuration settings using Pydantic."""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, ValidationError


class Settings(BaseSettings):
    """Application configuration settings."""

    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(2000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(0.3, env="OPENAI_TEMPERATURE")

    # API Configuration
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    debug: bool = Field(False, env="DEBUG")

    # CORS Configuration
    allowed_origins: list[str] = Field(
        ["*"],
        env="ALLOWED_ORIGINS",
    )

    # Trusted Hosts Configuration
    trusted_hosts: list[str] = Field(["*"], env="TRUSTED_HOSTS")

    # Rate Limiting
    rate_limit_per_minute: int = Field(30, env="RATE_LIMIT_PER_MINUTE")

    # MongoDB Configuration
    mongodb_uri: str = Field(..., env="MONGODB_URI")
    mongo_dbname: str = Field("diagrammatic", env="MONGO_DBNAME")
    mongo_collname: str = Field("problems", env="MONGO_COLLNAME")

    class Config:
        """Pydantic configuration to load from .env file."""

        env_file = ".env"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        s = Settings()
    except ValidationError as e:
        # Raise a helpful message in logs for missing required envs
        raise RuntimeError(f"Configuration error: {e}") from e
    return s
