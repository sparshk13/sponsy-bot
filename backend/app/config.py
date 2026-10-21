"""Application settings loaded from environment."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://sponsy_app:sponsy_pass@localhost:5432/sponsy"
    timezone: str = "Asia/Kolkata"
    public_url: str = "http://localhost"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_model_light: str = "gemini-2.0-flash"
    gemini_rpm: int = 12
    gemini_daily_call_cap: int = 800

    tavily_api_key: str = ""
    tavily_monthly_credit_cap: int = 800

    hunter_api_key: str = ""
    hunter_monthly_credit_cap: int = 40

    # Mail settings (SMTP and IMAP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "outreach@studenttechclub.org"
    smtp_tls: bool = True
    smtp_starttls: bool = True

    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_ssl: bool = True

    # Pacing and limits (R11, BUD-08)
    daily_send_cap: int = 30
    send_window_start_hour: int = 9
    send_window_end_hour: int = 18
    send_min_gap_seconds: int = 60
    send_jitter_max_seconds: int = 30
    weekdays_only: bool = True
    max_followups: int = 2
    followup_days: str = "4,5"
    brochures_upload_dir: str = "uploads/brochures"
    backup_age_recipient: str = ""
    trusted_proxies: str = "127.0.0.1,::1,caddy"
    api_rate_limit_per_minute: int = 120
    login_rate_limit_per_minute: int = 10

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        if v.startswith("postgresql://") and not v.startswith("postgresql+psycopg://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    @field_validator("daily_send_cap")
    @classmethod
    def validate_daily_send_cap(cls, v: int) -> int:
        if v > 40:
            raise ValueError("daily_send_cap cannot exceed 40 (PRD R11, BUD-08)")
        if v < 1:
            raise ValueError("daily_send_cap must be at least 1")
        return v



settings = Settings()
