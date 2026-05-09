"""Caveat AI backend configuration.

Per Constitution VIII, the production target model is
``gemma4:31b-instruct-q4_K_M`` (Gemma 4 31B Dense, Q4_K_M quantization),
which provides the 128K context window the pipeline relies on.

The development default is ``gemma4:e4b`` — sized to fit the laptops the
team builds on (e.g., M-series MacBook Air). Override at runtime via the
``CAVEAT_MODEL`` environment variable. Hardware auto-detection lands in
Sprint 5; until then, the operator chooses explicitly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from env (``CAVEAT_*``) and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="CAVEAT_",
        env_file=".env",
        extra="ignore",
    )

    # ``CAVEAT_MODEL`` (no ``_NAME`` suffix) overrides this. The
    # ``validation_alias`` wins over the env_prefix-derived name, so
    # ``CAVEAT_MODEL`` is the single switch documented in .env.example.
    model_name: str = Field(default="gemma4:e4b", validation_alias="CAVEAT_MODEL")
    host: str = "127.0.0.1"
    port: int = 8787
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".caveat")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Tests that mutate ``CAVEAT_*`` env vars must call
    ``get_settings.cache_clear()`` before re-reading.
    """
    return Settings()
