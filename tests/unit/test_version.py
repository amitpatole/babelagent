"""Version drift-guard: __version__ must match pyproject and CITATION.cff."""

from __future__ import annotations

import tomllib
from pathlib import Path

import babelagent

_ROOT = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    data = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]


def _citation_version() -> str:
    for line in (_ROOT / "CITATION.cff").read_text().splitlines():
        if line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    raise AssertionError("no version in CITATION.cff")


def test_version_is_consistent():
    assert babelagent.__version__ == _pyproject_version()
    assert babelagent.__version__ == _citation_version()
