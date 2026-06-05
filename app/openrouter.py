from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app import config


class OpenRouterRateLimitError(RuntimeError):
    def __init__(self, model: str, message: str, status_code: int = 429) -> None:
        super().__init__(message)
        self.model = model
        self.status_code = status_code


@dataclass(frozen=True)
class OpenRouterModelInfo:
    id: str
    name: str
    canonical_slug: str | None = None
    context_length: int | None = None
    prompt_price: str = "0"
    completion_price: str = "0"
    weekly_tokens: int | None = None


def validate_free_openrouter_model(model: str) -> None:
    if not model.endswith(":free"):
        raise RuntimeError(
            f"Unsafe OpenRouter model: {model}. "
            "Use only models ending with ':free' to avoid paid usage."
        )


def _api_url(path: str) -> str:
    return f"{config.OPENROUTER_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _headers(require_api_key: bool = False) -> dict[str, str]:
    if require_api_key and not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to .env before using OpenRouter.")

    headers = {
        "Content-Type": "application/json",
        "X-OpenRouter-Title": config.OPENROUTER_APP_TITLE,
    }
    if config.OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {config.OPENROUTER_API_KEY}"
    if config.OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = config.OPENROUTER_HTTP_REFERER
    return headers


def get_active_openrouter_model() -> str:
    path = config.OPENROUTER_ACTIVE_MODEL_PATH
    if path.exists():
        model = path.read_text(encoding="utf-8").strip()
        if model:
            validate_free_openrouter_model(model)
            return model
    validate_free_openrouter_model(config.OPENROUTER_MODEL)
    return config.OPENROUTER_MODEL


def set_active_openrouter_model(model: str) -> str:
    validate_free_openrouter_model(model)
    path = config.OPENROUTER_ACTIVE_MODEL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.strip(), encoding="utf-8")
    return model


def _is_free_model_payload(model: dict[str, Any]) -> bool:
    model_id = str(model.get("id", ""))
    pricing = model.get("pricing") or {}
    return (
        model_id.endswith(":free")
        and str(pricing.get("prompt", "0")) == "0"
        and str(pricing.get("completion", "0")) == "0"
    )


def list_free_openrouter_models(timeout: float | None = None) -> list[OpenRouterModelInfo]:
    response = requests.get(
        _api_url("models"),
        headers=_headers(require_api_key=False),
        timeout=timeout or config.OPENROUTER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    models: list[OpenRouterModelInfo] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict) or not _is_free_model_payload(item):
            continue
        pricing = item.get("pricing") or {}
        models.append(
            OpenRouterModelInfo(
                id=str(item.get("id")),
                name=str(item.get("name") or item.get("id")),
                canonical_slug=str(item.get("canonical_slug") or item.get("id")),
                context_length=item.get("context_length"),
                prompt_price=str(pricing.get("prompt", "0")),
                completion_price=str(pricing.get("completion", "0")),
            )
        )
    return sorted(models, key=lambda model: model.id)


def _rankings_window(days: int = 7) -> tuple[str, str]:
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=max(1, days) - 1)
    return start.isoformat(), end.isoformat()


def fetch_global_free_model_token_rankings(days: int = 7, limit: int = 5) -> list[OpenRouterModelInfo]:
    free_models = list_free_openrouter_models()
    free_by_slug: dict[str, OpenRouterModelInfo] = {}
    for model in free_models:
        free_by_slug[model.id] = model
        if model.canonical_slug:
            free_by_slug[model.canonical_slug] = model

    start_date, end_date = _rankings_window(days=days)
    response = requests.get(
        _api_url("datasets/rankings-daily"),
        headers=_headers(require_api_key=True),
        params={"start_date": start_date, "end_date": end_date},
        timeout=config.OPENROUTER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    totals: dict[str, int] = {}
    for row in payload.get("data", []):
        if not isinstance(row, dict):
            continue
        slug = str(row.get("model_permaslug") or "")
        if slug == "other" or slug not in free_by_slug:
            continue
        model = free_by_slug[slug]
        totals[model.id] = totals.get(model.id, 0) + int(row.get("total_tokens") or 0)

    ranked: list[OpenRouterModelInfo] = []
    models_by_id = {model.id: model for model in free_models}
    for model_id, total_tokens in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]:
        model = models_by_id[model_id]
        ranked.append(
            OpenRouterModelInfo(
                id=model.id,
                name=model.name,
                canonical_slug=model.canonical_slug,
                context_length=model.context_length,
                prompt_price=model.prompt_price,
                completion_price=model.completion_price,
                weekly_tokens=total_tokens,
            )
        )
    return ranked


def ranked_free_openrouter_models(limit: int = 5) -> list[OpenRouterModelInfo]:
    try:
        global_ranked = fetch_global_free_model_token_rankings(days=7, limit=limit)
        if global_ranked:
            return global_ranked
    except Exception:
        pass

    free_models = list_free_openrouter_models()
    by_id = {model.id: model for model in free_models}

    ranked_ids: list[str] = []
    try:
        from app.database import fetch_openrouter_usage_ranking

        ranked_ids = [
            row["model_id"]
            for row in fetch_openrouter_usage_ranking(limit=50)
            if str(row.get("model_id", "")).endswith(":free")
        ]
    except Exception:
        ranked_ids = []

    selected: list[OpenRouterModelInfo] = []
    seen: set[str] = set()
    for model_id in [get_active_openrouter_model(), config.OPENROUTER_MODEL, *ranked_ids]:
        if model_id in by_id and model_id not in seen:
            selected.append(by_id[model_id])
            seen.add(model_id)
        if len(selected) >= limit:
            return selected

    for model in free_models:
        if model.id not in seen:
            selected.append(model)
            seen.add(model.id)
        if len(selected) >= limit:
            break
    return selected


def _message_to_openrouter(message: BaseMessage) -> dict[str, Any]:
    role_map = {
        "human": "user",
        "ai": "assistant",
        "system": "system",
        "tool": "tool",
        "function": "tool",
    }
    role = role_map.get(message.type, "user")
    content = message.content if isinstance(message.content, str) else str(message.content)
    payload: dict[str, Any] = {"role": role, "content": content}
    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id
    return payload


def _record_usage(model: str, usage: dict[str, Any] | None, status: str, raw_json: dict[str, Any] | None) -> None:
    try:
        from app.database import record_openrouter_usage

        record_openrouter_usage(
            model_id=model,
            usage=usage or {},
            request_status=status,
            raw_json=raw_json or {},
        )
    except Exception:
        return


class OpenRouterFreeChatModel(BaseChatModel):
    temperature: float = 0.1
    max_tokens: int | None = None
    timeout: float | None = None

    @property
    def _llm_type(self) -> str:
        return "openrouter_free_chat"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        model = get_active_openrouter_model()
        validate_free_openrouter_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_message_to_openrouter(message) for message in messages],
            "temperature": self.temperature,
        }
        max_tokens = kwargs.get("max_tokens") or self.max_tokens or config.OPENROUTER_MAX_TOKENS
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        if stop:
            payload["stop"] = stop

        response = requests.post(
            _api_url("chat/completions"),
            headers=_headers(require_api_key=True),
            json=payload,
            timeout=self.timeout or config.OPENROUTER_TIMEOUT_SECONDS,
        )
        if response.status_code == 429:
            raw = _safe_json(response)
            _record_usage(model, None, "rate_limited", raw)
            message = _error_message(raw) or response.text or "OpenRouter free model rate limit reached."
            raise OpenRouterRateLimitError(model=model, message=message)
        if response.status_code >= 400:
            raw = _safe_json(response)
            _record_usage(model, None, f"http_{response.status_code}", raw)
            message = _error_message(raw) or response.text
            raise RuntimeError(f"OpenRouter request failed for {model}: {message}")

        data = response.json()
        usage = data.get("usage") or {}
        response_model = str(data.get("model") or model)
        validate_free_openrouter_model(model)
        _record_usage(response_model if response_model.endswith(":free") else model, usage, "success", data)

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices for {model}.")
        message_payload = choices[0].get("message") or {}
        content = message_payload.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        ai_message = AIMessage(
            content=content,
            response_metadata={
                "model": response_model,
                "usage": usage,
                "finish_reason": choices[0].get("finish_reason"),
                "native_finish_reason": choices[0].get("native_finish_reason"),
            },
        )
        return ChatResult(
            generations=[ChatGeneration(message=ai_message)],
            llm_output={"model": response_model, "usage": usage},
        )


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error or "")


def build_openrouter_llm(temperature: float = 0.1) -> OpenRouterFreeChatModel:
    return OpenRouterFreeChatModel(
        temperature=temperature,
        max_tokens=config.OPENROUTER_MAX_TOKENS,
        timeout=config.OPENROUTER_TIMEOUT_SECONDS,
    )
