"""Runtime settings, read from the environment and `.env` (see `.env.example`)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    site_source: Literal["mock", "pipeline"] = "mock"
    anthropic_api_key: str | None = None
    ai_search_model: str = "claude-haiku-4-5-20251001"
    # Comma-separated, e.g. "http://localhost:5173,http://127.0.0.1:5173".
    cors_origins: str = "http://localhost:5173"
    golden_dir: Path = REPO_ROOT / "fixtures" / "golden"
    mock_generated_dir: Path = REPO_ROOT / "fixtures" / "mock" / "generated"
    mock_evidence_dir: Path = REPO_ROOT / "fixtures" / "mock" / "ui-draft"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
