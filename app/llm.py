from __future__ import annotations

import re

from app.openrouter import build_openrouter_llm


def build_openrouter_free_llm(temperature: float = 0.1):
    return build_openrouter_llm(temperature=temperature)


def build_chat_llm(backend: str | None = None, temperature: float = 0.1):
    selected = (backend or "openrouter").lower()
    if selected in {"openrouter", "openrouter_free", "free"}:
        return build_openrouter_free_llm(temperature=temperature)
    raise RuntimeError(f"Unsupported LLM backend: {selected}")


def strip_hidden_reasoning(text: str) -> str:
    # Some free reasoning models can emit <think> blocks. Keep UI/parser output clean.
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
