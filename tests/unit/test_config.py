"""Review fix: Settings rejects nonsensical values instead of silently misbehaving."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from babelagent.config import Settings


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_timeout_s": -1},
        {"request_timeout_s": 0},
        {"max_body_bytes": 0},
        {"max_concurrency": 0},
        {"port": 99999},
        {"port": 0},
    ],
)
def test_settings_rejects_bad_values(kwargs):
    with pytest.raises(ValidationError):
        Settings(**kwargs)


def test_settings_defaults_valid():
    s = Settings()
    assert s.port == 8099 and s.request_timeout_s == 60.0 and s.max_concurrency == 8
