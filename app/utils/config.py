"""Application configuration settings using Pydantic."""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, ValidationError


class Settings(BaseSettings):
    """Application configuration settings."""

    # OpenAI Configuration
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", validation_alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(2000, validation_alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(0.3, validation_alias="OPENAI_TEMPERATURE")

    # API Configuration
    api_host: str = Field("0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(8000, validation_alias="API_PORT")
    debug: bool = Field(False, validation_alias="DEBUG")

    # CORS Configuration
    allowed_origins: list[str] = Field(
        ["*"],
        validation_alias="ALLOWED_ORIGINS",
    )

    # Trusted Hosts Configuration
    trusted_hosts: list[str] = Field(["*"], validation_alias="TRUSTED_HOSTS")

    # Rate Limiting
    rate_limit_per_minute: int = Field(30, validation_alias="RATE_LIMIT_PER_MINUTE")

    # JWT Configuration
    jwt_secret_key: str = Field(..., validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_token_expire_hours: int = Field(
        24, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_HOURS"
    )

    # Google OAuth Configuration
    google_client_id: str = Field(..., validation_alias="GOOGLE_CLIENT_ID")

    # AWS DynamoDB Configuration
    aws_region: str = Field("us-east-1", validation_alias="AWS_REGION")
    aws_access_key_id: str = Field(..., validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., validation_alias="AWS_SECRET_ACCESS_KEY")
    dynamodb_users_table: str = Field(
        "diagrammatic_users", validation_alias="DYNAMODB_USERS_TABLE"
    )
    dynamodb_diagrams_table: str = Field(
        "diagrammatic_diagrams", validation_alias="DYNAMODB_DIAGRAMS_TABLE"
    )
    dynamodb_problems_table: str = Field(
        "diagrammatic_problems", validation_alias="DYNAMODB_PROBLEMS_TABLE"
    )
    dynamodb_attempts_table: str = Field(
        "diagrammatic_problem_attempts", validation_alias="DYNAMODB_ATTEMPTS_TABLE"
    )
    # Frontend URL (used to build public solution links)
    frontend_url: str = Field(
        "https://diagrammatic.next-zen.dev",
        validation_alias="FRONTEND_URL",
    )

    components_table_name: str = Field(
        "diagrammatic_components", validation_alias="DYNAMODB_COMPONENTS_TABLE"
    )
    dynamodb_walkthroughs_table: str = Field(
        "diagrammatic_guided_walkthroughs", validation_alias="DYNAMODB_WALKTHROUGHS_TABLE"
    )

    # Spritesheet key prefix (sheets are stored under the analytics bucket)
    sprites_key_prefix: str = Field(
        "spritesheet", validation_alias="SPRITES_KEY_PREFIX"
    )

    # Primary S3 bucket used by the application for all S3 writes.
    # This single env var replaces prior `TRAINING_S3_BUCKET` / `S3_BUCKET`.
    analytics_s3_bucket: str = Field(..., validation_alias="ANALYTICS_S3_BUCKET")

    # HMAC secret used to pseudonymize user IDs for analytics storage.
    analytics_hmac_secret: str | None = Field(
        None, validation_alias="ANALYTICS_HMAC_SECRET"
    )

    class Config:
        """Pydantic configuration to load from .env file."""

        env_file = ".env"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        s = Settings()  # type: ignore[call-arg]
    except ValidationError as e:
        # Raise a helpful message in logs for missing required envs
        raise RuntimeError(f"Configuration error: {e}") from e
    return s
