"""Application settings — all values come from environment variables / .env.

Never hardcode secrets in code. Add new settings here, then document them
in the root .env.example file.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
# careerpilot/  (project root)
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ─────────────────────────────────────────────────
    app_name: str = "CareerPilot AI"
    api_prefix: str = "/api/v1"
    debug: bool = True

    # ── Database ─────────────────────────────────────────────
    database_url: str = f"sqlite:///{(DATA_DIR / 'careerpilot.db').as_posix()}"
    auto_create_tables: bool = True  # dev only; use Alembic in production

    # ── Auth ─────────────────────────────────────────────────
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # ── PII encryption (Fernet) ──────────────────────────────
    encryption_key: str = ""

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Timezone ─────────────────────────────────────────────
    timezone: str = "Africa/Nairobi"

    # ── Uploads ──────────────────────────────────────────────
    max_upload_mb: int = 20

    # ── LLM providers (Phase 2+) ─────────────────────────────
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # ── Discovery sources (Phase 2: JobScout) ─────────────────
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_countries: list[str] = ["ke"]
    google_cse_key: str = ""
    google_cse_cx: str = ""
    serper_key: str = ""
    tavily_key: str = ""

    # ── Scheduler ─────────────────────────────────────────────
    enable_scheduler: bool = True
    jobs_search_hours: str = "0,8,16"  # cron hours (local timezone), 3×/day
    scholarship_search_hours: str = "7,19"  # scholarship discovery, 2×/day

    # ── Relevance gates ───────────────────────────────────────
    # Jobs (Phase 2): skip obvious out-of-scope listings (sales/marketing/design...)
    jobs_relevance_filter: bool = True
    # Scholarships (Phase 3): keep scholarship/fellowship/grant/Master's signals only
    scholarship_relevance_filter: bool = True

    # ── Matching (Phase 5) ────────────────────────────────────
    high_match_threshold: float = 80.0
    eligibility_eligible_threshold: float = 70.0
    eligibility_possible_threshold: float = 40.0
    open_to_international: bool = False  # set true to score international roles higher

    # ── Notifications (Phase 5+) ─────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Helpers ──────────────────────────────────────────────
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def upload_dir(self) -> Path:
        return DATA_DIR / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
