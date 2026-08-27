"""Runtime settings, loaded from environment variables (``BABELAGENT_*``).

Secrets (e.g. ``api_token``) are read only from the environment. They are never
hard-coded and never serialized into a topology. ``config_dir`` is exposed as a
conventional location for future file-based config but is not read today.
"""

from __future__ import annotations

from pathlib import Path

import platformdirs
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path(platformdirs.user_config_dir("babelagent"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BABELAGENT_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # REST service (babelagent.io.rest)
    api_token: str | None = None
    host: str = "127.0.0.1"
    port: int = 8099
    max_body_bytes: int = 8 * 1024 * 1024  # 8 MiB request cap
    max_concurrency: int = 8
    request_timeout_s: float = 60.0

    config_dir: Path = Field(default=_CONFIG_DIR)


def load_settings(**overrides: object) -> Settings:
    settings = Settings()
    if overrides:
        settings = settings.model_copy(update=overrides)
    return settings
