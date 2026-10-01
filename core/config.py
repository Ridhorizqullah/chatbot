from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Konfigurasi aplikasi berbasis pydantic-settings."""

    # Server App
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM (Google Gemini)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash", alias="GEMINI_MODEL")
    embedding_model: str = Field(default="gemini-embedding-001", alias="EMBEDDING_MODEL")

    # Supabase (Database, pgvector, Storage)
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket_name: str = Field(default="crop-symptoms", alias="SUPABASE_BUCKET_NAME")

    # WhatsApp Meta Cloud API
    meta_wa_phone_number_id: str = Field(default="", alias="META_WA_PHONE_NUMBER_ID")
    meta_wa_access_token: str = Field(default="", alias="META_WA_ACCESS_TOKEN")
    meta_wa_verify_token: str = Field(default="tanipintar_webhook_verify_token_secret", alias="META_WA_VERIFY_TOKEN")
    meta_graph_version: str = Field(default="v20.0", alias="META_GRAPH_VERSION")

    # WhatsApp Provider (meta atau waha)
    whatsapp_provider: str = Field(default="waha", alias="WHATSAPP_PROVIDER")
    waha_base_url: str = Field(default="http://localhost:3000", alias="WAHA_BASE_URL")
    waha_session: str = Field(default="default", alias="WAHA_SESSION")

    # Guardrails & Admin
    confidence_threshold: float = Field(default=0.70, alias="CONFIDENCE_THRESHOLD")
    admin_api_key: str = Field(default="tanipintar_admin_secret_2026", alias="ADMIN_API_KEY")

    # Weather API (WeatherAPI.com)
    weather_api_key: str = Field(default="", alias="WEATHER_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
