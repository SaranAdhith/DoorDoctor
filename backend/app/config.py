"""Application configuration loaded from the environment."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Values come from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DoorDoctor API"
    api_prefix: str = "/api/v1"
    environment: str = Field(default="development")

    database_url: str = Field(default="sqlite:///./doordoc.db", alias="DATABASE_URL")
    jwt_secret: str = Field(default="change-this-in-development", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS")
    # Where password-reset links point. The API never serves that page.
    frontend_base_url: str = Field(default="http://localhost:5173", alias="FRONTEND_BASE_URL")

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def is_development(self) -> bool:
        """Gates development-only affordances such as `debug_reset_url`."""
        return self.environment.strip().lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list; `*` disables the allow-list."""
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
