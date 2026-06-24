from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "NEXUS ANON"
    data_dir: Path = Path("data")
    database_path: Path = Path("data/nexus_anon.sqlite3")
    ollama_url: str = "http://127.0.0.1:11434"
    default_model: str = "NEXUS-anon:latest"
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
    ]
    max_upload_mb: int = 100

    class Config:
        env_file = ".env"
        env_prefix = "NEXUS_ANON_"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
