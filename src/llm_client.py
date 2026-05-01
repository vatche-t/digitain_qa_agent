"""
LLM client abstraction.

Why both providers?
    1. Digitain shouldn't be locked to one vendor — agent cost/quality varies
       per-task and per-quarter as models update.
    2. Lets you A/B test which model writes more reliable test plans.
    3. The "switch in one line" pattern is a sales point: "we don't pick
       your AI vendor for you."

The agent only uses ONE method on these clients: `complete()`.
Adding Gemini, local Llama, etc. is a 30-line file.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Literal

Provider = Literal["claude", "openai"]


class LLMClient(ABC):
    """Minimal LLM interface the agent depends on."""

    name: str

    @abstractmethod
    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        """Return the model's text response."""


class ClaudeClient(LLMClient):
    """Anthropic Claude via the official SDK."""

    name = "claude"

    def __init__(self, model: str = "claude-sonnet-4-5-20250929") -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic SDK not installed. Run: pip install anthropic"
            ) from e

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY env var is required for Claude.")

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        # Claude doesn't have a json_mode flag — we instruct via system prompt.
        sys_prompt = system
        if json_mode:
            sys_prompt += "\n\nReply with a single valid JSON object. No prose, no code fences."

        msg = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text


class OpenAIClient(LLMClient):
    """OpenAI GPT-4o family."""

    name = "openai"

    def __init__(self, model: str = "gpt-4o") -> None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai SDK not installed. Run: pip install openai"
            ) from e

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY env var is required for OpenAI.")

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        kwargs = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 2048,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


def get_client(provider: Provider, model: str | None = None) -> LLMClient:
    """Factory. Used by the CLI."""
    if provider == "claude":
        return ClaudeClient(model=model) if model else ClaudeClient()
    if provider == "openai":
        return OpenAIClient(model=model) if model else OpenAIClient()
    raise ValueError(f"Unknown provider: {provider}")


def safe_json_parse(text: str) -> dict:
    """LLMs sometimes wrap JSON in code fences despite instructions. Be lenient."""
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ```
        text = text.split("```", 2)[1]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())
