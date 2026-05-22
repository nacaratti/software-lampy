from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAMPY_", env_file=".env", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    max_concurrent_jobs: int = 2
    job_ttl_seconds: int = 3600
    progress_min_interval_seconds: float = 0.1  # at most 10 Hz


settings = Settings()
