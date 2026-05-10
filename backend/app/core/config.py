from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = "http://localhost:5173"
    MISTRAL_API_KEY: str

    class Config:
        env_file = ".env"

    @property
    def sync_database_url(self) -> str:
        """Fixes 'postgres://' to 'postgresql://' for SQLAlchemy 1.4+ / 2.0+ compatibility."""
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self.DATABASE_URL

settings = Settings()
