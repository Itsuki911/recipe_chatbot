from __future__ import annotations

import re

from app import config


def build_qwen_llm(temperature: float = 0.1):
    # Ollama exposes an OpenAI-compatible API, so LangChain can call Qwen via ChatOpenAI.
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("Install langchain-openai to use Ollama Qwen.") from exc

    return ChatOpenAI(
        model=config.QWEN_MODEL,
        base_url=config.QWEN_BASE_URL,
        api_key=config.QWEN_API_KEY,
        temperature=temperature,
    )


def build_gemini_llm(temperature: float = 0.1):
    if not config.GOOGLE_API_KEY:
        raise RuntimeError(
            "Gemini LLM backend is selected, but GOOGLE_API_KEY is not set. "
            "Add GOOGLE_API_KEY to .env. The key must stay out of git."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        temperature=temperature,
        google_api_key=config.GOOGLE_API_KEY,
    )


def build_chat_llm(backend: str | None = None, temperature: float = 0.1):
    selected = (backend or config.MAIN_LLM_BACKEND or "qwen").lower()
    if selected in {"qwen", "ollama"}:
        return build_qwen_llm(temperature=temperature)
    if selected in {"gemini", "google"}:
        return build_gemini_llm(temperature=temperature)
    raise RuntimeError(f"Unsupported LLM backend: {selected}")


def strip_hidden_reasoning(text: str) -> str:
    # Qwen3 can emit <think> blocks depending on runtime settings. Keep UI/parser output clean.
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
