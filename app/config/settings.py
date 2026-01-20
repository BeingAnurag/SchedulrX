from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = "SchedulrX"
    debug: bool = True
    postgres_dsn: str = Field("postgresql://user:password@localhost:5432/schedulrx", env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    solver_slot_size_minutes: int = 30
    solver_time_limit_seconds: int = 10

    class Config:
        env_file = ".env"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
