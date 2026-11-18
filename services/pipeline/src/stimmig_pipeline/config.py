"""Runtime configuration, read from environment variables (prefix ``STIMMIG_``)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STIMMIG_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/stimmig_pipeline"

    # OIDC: the identity service that signs access tokens, and this API's resource id.
    oidc_issuer: str = "http://localhost:4000"
    api_audience: str = "urn:stimmig:api"
    # Override the JWKS location (defaults to the issuer's discovery document).
    jwks_url: str | None = None

    # Origins allowed to call the API from a browser. The admin app calls it
    # server-side, so this is only for local tooling.
    cors_origins: list[str] = Field(default_factory=list)

    # LLM: "live", "record" or "replay". Replay needs no API key.
    llm_mode: str = "live"
    model: str = "claude-sonnet-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
