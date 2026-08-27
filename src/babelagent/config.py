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

    # REST service (babelagent.io.rest). Constraints make an operator typo fail
    # fast (a bad env var) instead of silently rejecting all traffic / timing out.
    api_token: str | None = None
    host: str = "127.0.0.1"
    port: int = Field(default=8099, ge=1, le=65535)
    max_body_bytes: int = Field(default=8 * 1024 * 1024, gt=0)  # 8 MiB request cap
    max_concurrency: int = Field(default=8, ge=1)
    request_timeout_s: float = Field(default=60.0, gt=0)

    config_dir: Path = Field(default=_CONFIG_DIR)


def load_settings(**overrides: object) -> Settings:
    settings = Settings()
    if overrides:
        settings = settings.model_copy(update=overrides)
    return settings
