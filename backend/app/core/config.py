from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./evothermguard.db"
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_mode: str = "demo"
    model_checkpoint: str = ""
    storage_path: str = "./storage"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""
    max_upload_bytes: int = 10 * 1024 * 1024
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def storage_root(self) -> Path:
        return Path(self.storage_path).resolve()

    @property
    def allowed_origins(self) -> list[str]:
        """Return the configured browser origins without duplicate entries."""
        origins = [self.frontend_url, *(origin.strip() for origin in self.cors_origins.split(","))]
        return list(dict.fromkeys(origin for origin in origins if origin))

settings = Settings()
