from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central place for all environment-driven config.
    Values are read from a .env file (see .env.example) or real
    environment variables in production (Railway/Render/Fly secrets).
    """

    supabase_url: str
    supabase_jwks_url: str  # e.g. https://<ref>.supabase.co/auth/v1/.well-known/jwks.json

    database_url: str

    groq_api_key: str

    # Shared secret for the /tna/scan-all endpoint, called by a scheduled
    # job (e.g. GitHub Actions cron) rather than a logged-in user.
    cron_secret: str = "change-me"

    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
