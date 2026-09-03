"""
Centralized application settings, loaded from environment variables / .env.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = "http://localhost:5173"

    # Database - empty DATABASE_URL means "use local SQLite" (zero-setup dev mode)
    DATABASE_URL: str = ""

    # Storage
    STORAGE_DRIVER: str = "local"  # "local" | "supabase"
    LOCAL_STORAGE_DIR: str = "./storage_local"

    SUPABASE_S3_ENDPOINT: str = ""
    SUPABASE_S3_REGION: str = "us-east-1"
    SUPABASE_S3_ACCESS_KEY_ID: str = ""
    SUPABASE_S3_SECRET_ACCESS_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "drive-files"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/auth/google/callback"

    MAX_UPLOAD_SIZE_MB: int = 100
    RATE_LIMIT_DEFAULT: str = "100/minute"

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return "sqlite:///./app.db"

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
