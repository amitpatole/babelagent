"""Adapt an LLM provider (Anthropic / OpenAI / Ollama) as a graph agent.

Providers are imported lazily; installing the matching extra is required at
call time. API keys are resolved from the environment / ``~/.config`` only.
"""

from __future__ import annotations

import os
from typing import Any

from ..core.agent import Context
from ..core.errors import MissingDependencyError
from ..core.message import Message

# Default to the latest, most capable Claude model (house rule).
DEFAULT_MODEL = "claude-opus-4-8"


class LLM:
    """A prompt-in / text-out worker backed by an LLM provider.

    The node's input payload is substituted into ``prompt`` via ``{input}``
    (or sent as the whole user message when ``prompt`` is omitted).
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        prompt: str | None = None,
        provider: str | None = None,
        system: str | None = None,
        name: str | None = None,
        max_tokens: int = 1024,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.prompt = prompt
        self.provider = provider or _infer_provider(model)
        self.system = system
        self.name = name or f"llm:{model}"
        self.max_tokens = max_tokens
        self._api_key = api_key

    def _render(self, payload: Any) -> str:
        if self.prompt is None:
            return str(payload)
        try:
            return self.prompt.format(input=payload)
        except (KeyError, IndexError):
            return f"{self.prompt}\n\n{payload}"

    async def run(self, message: Message, ctx: Context) -> Message:
        prompt = self._render(message.payload)
        if self.provider == "anthropic":
            text = await self._anthropic(prompt)
        elif self.provider == "openai":
            text = await self._openai(prompt)
        elif self.provider == "ollama":
            text = await self._ollama(prompt)
        else:
            raise MissingDependencyError(f"provider {self.provider!r}", "cloud")
        return message.with_payload(text, node=self.name, model=self.model)

    async def _anthropic(self, message: str) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise MissingDependencyError("Anthropic LLM", "cloud") from exc
        client = anthropic.AsyncAnthropic(
            api_key=self._api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": message}],
        }
        if self.system:
            kwargs["system"] = self.system
        resp = await client.messages.create(**kwargs)
        return "".join(block.text for block in resp.content if block.type == "text")

    async def _openai(self, message: str) -> str:
        try:
            import openai
        except ImportError as exc:
            raise MissingDependencyError("OpenAI LLM", "cloud") from exc
        client = openai.AsyncOpenAI(api_key=self._api_key or os.environ.get("OPENAI_API_KEY"))
        messages = ([{"role": "system", "content": self.system}] if self.system else []) + [
            {"role": "user", "content": message}
        ]
        resp = await client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=self.max_tokens
        )
        return resp.choices[0].message.content or ""

    async def _ollama(self, message: str) -> str:
        try:
            import ollama
        except ImportError as exc:
            raise MissingDependencyError("Ollama LLM", "ollama") from exc
        client = ollama.AsyncClient()
        resp = await client.chat(
            model=self.model, messages=[{"role": "user", "content": message}]
        )
        return resp["message"]["content"]


def _infer_provider(model: str) -> str:
    m = model.lower()
    if m.startswith("claude") or "anthropic" in m:
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4")) or "openai" in m:
        return "openai"
    return "ollama"
