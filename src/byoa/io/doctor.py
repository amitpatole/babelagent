"""``byoa doctor`` — light environment diagnostics (never imports heavy deps)."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def run_checks() -> list[Check]:
    """Probe which optional adapter families are available. Zero-config."""
    from .. import __version__

    checks = [Check("byoa", True, f"version {__version__}")]
    checks.append(Check("core deps (pydantic, httpx, typer)",
                        _has("pydantic") and _has("httpx") and _has("typer"),
                        "base wheel"))
    families = {
        "mcp": ("MCP adapter", "mcp"),
        "anthropic": ("Anthropic LLM", "cloud"),
        "openai": ("OpenAI LLM", "cloud"),
        "ollama": ("Ollama LLM", "ollama"),
        "langchain_core": ("LangChain adapter", "frameworks"),
        "fastapi": ("REST service", "serve"),
    }
    for module, (label, extra) in families.items():
        present = _has(module)
        detail = "available" if present else f"install byoa-sdk[{extra}]"
        checks.append(Check(label, present, detail))
    return checks


def format_checks(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        mark = "✓" if c.ok else "·"
        lines.append(f"  {mark} {c.name:<28} {c.detail}")
    return "\n".join(lines)
