from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import bs4
import requests
from pydantic import BaseModel, Field

from app import config
from app.llm import build_chat_llm, strip_hidden_reasoning
from app.rag_chatbot import _headers


class CrawlFinding(BaseModel):
    title: str = Field(description="ページまたは抽出内容のタイトル")
    summary: str = Field(description="ユーザーが求めた情報に対する要約")
    key_points: list[str] = Field(description="重要なポイント")
    useful_details: list[str] = Field(description="追加で役立つ具体情報")


@dataclass
class Crawl4AIPerformanceResult:
    # UIでcrawl4aiの性能を見やすく表示するための結果オブジェクトです。
    user_request: str
    search_query: str
    candidate_urls: list[str]
    selected_url: str
    attempted_urls: list[str]
    extracted_content: str
    markdown_chars: int
    cleaned_html_chars: int
    timings: dict[str, float]
    success: bool
    error: str | None = None
    progress_messages: list[str] | None = None
    model_id: str = ""
    extraction_mode: str = "llm"
    rate_limited: bool = False
    fallback_reason: str = ""


def _run_async(coro):
    # Streamlitの実行環境にevent loopがある場合でも、async処理を同期関数から呼べるようにします。
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_holder: list[object] = []
    error_holder: list[BaseException] = []

    def runner() -> None:
        try:
            result_holder.append(asyncio.run(coro))
        except BaseException as exc:
            error_holder.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error_holder:
        raise error_holder[0]
    return result_holder[0]


def _build_llm():
    return build_chat_llm(config.STRUCTURED_LLM_BACKEND, temperature=0.0)


def build_search_query(user_request: str) -> str:
    # ユーザーの「〜な情報が欲しい」を、検索エンジン向けの短いクエリに変換します。
    llm = _build_llm()
    response = llm.invoke(
        [
            (
                "system",
                "Create one concise web search query for finding reliable information. "
                "Return only the query text. Do not include quotes or commentary.",
            ),
            ("human", user_request),
        ]
    )
    query = strip_hidden_reasoning(str(response.content)).strip().strip('"')
    return query or user_request


def _extract_duckduckgo_url(href: str) -> str:
    # DuckDuckGo HTML検索結果のリダイレクトURLから、実URLを取り出します。
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return unquote(params["uddg"][0])
    return href


def discover_urls_for_query(search_query: str, max_results: int = 5) -> list[str]:
    # 特定URLをユーザーに指定させず、生成した検索クエリから候補URLを集めます。
    search_url = f"https://duckduckgo.com/html/?q={quote_plus(search_query)}"
    response = requests.get(search_url, headers=_headers(), timeout=30)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a, a.result__url, a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        url = _extract_duckduckgo_url(href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if "duckduckgo.com" in parsed.netloc or url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= max_results:
            break
    return urls


def select_best_url(user_request: str, search_query: str, candidate_urls: list[str]) -> str:
    # OpenRouter free modelのリクエスト数を節約するため、URL選択はLLMではなく軽いスコア式にします。
    # LLMは「検索クエリ作成」と「crawl4ai LLM抽出」で使います。
    if not candidate_urls:
        raise RuntimeError("No candidate URLs were found for the generated search query.")

    query_terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9]+", search_query) if len(term) > 2}

    def score(url: str) -> int:
        parsed = urlparse(url)
        haystack = f"{parsed.netloc} {parsed.path}".lower()
        value = sum(2 for term in query_terms if term in haystack)
        if any(marker in haystack for marker in ("docs", "documentation", "official", "guide")):
            value += 4
        if any(marker in haystack for marker in ("blog", "qiita", "zenn", "medium", "csdn")):
            value -= 2
        return value

    return max(candidate_urls, key=score)


def _json_or_text(value: str) -> str:
    # extracted_contentがJSON文字列なら整形して表示し、JSONでなければそのまま返します。
    try:
        return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return value


def _is_empty_extraction(value: str) -> bool:
    stripped = value.strip()
    if stripped in {"", "{}", "[]", "null"}:
        return True
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return parsed in ({}, []) or parsed is None


def is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "openrouterratelimiterror",
            "rate limit",
            "rate-limited",
            "free-models-per-day",
            "quota",
            "usage limit",
            "provider returned error",
        )
    )


def active_crawl4ai_model_id() -> str:
    from app.openrouter import get_active_openrouter_model, validate_free_openrouter_model

    model_id = get_active_openrouter_model()
    validate_free_openrouter_model(model_id)
    return model_id


async def crawl_plain_content(url: str) -> tuple[str, int, int]:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

    crawl_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=80000,
        word_count_threshold=1,
    )
    async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
        result = await crawler.arun(url=url, config=crawl_config)
    if not result.success:
        raise RuntimeError(result.error_message or "crawl4ai plain extraction failed.")

    markdown = str(result.markdown or "").strip()
    cleaned_html = str(result.cleaned_html or "").strip()
    if markdown:
        text = markdown
    else:
        text = bs4.BeautifulSoup(cleaned_html, "html.parser").get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise RuntimeError("crawl4ai plain extraction returned empty content.")
    preview = text[:5000]
    payload = {
        "title": "Fallback non-LLM crawl result",
        "summary": preview,
        "key_points": [],
        "useful_details": [
            "OpenRouter free model制限に達したため、LLM抽出ではなく通常抽出で表示しました。",
            f"Source URL: {url}",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2), len(markdown), len(cleaned_html)


async def crawl_and_extract_with_llm(url: str, user_request: str, model_id: str | None = None) -> tuple[str, int, int]:
    # 公式資料のLLMExtractionStrategy例に沿って、crawl4aiでクロールとLLM抽出を同時に実行します。
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig, LLMConfig
    from crawl4ai import LLMExtractionStrategy

    from app.openrouter import validate_free_openrouter_model

    model_id = model_id or active_crawl4ai_model_id()
    validate_free_openrouter_model(model_id)
    provider = f"openrouter/{model_id}"
    api_token = config.OPENROUTER_API_KEY
    base_url = None
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider=provider, api_token=api_token, base_url=base_url),
        schema=CrawlFinding.model_json_schema(),
        extraction_type="schema",
        instruction=(
            "Extract information that answers the user's request. "
            "Return valid JSON matching the schema. "
            "Write all user-facing JSON string values in the same language as the user's request unless they ask otherwise. "
            f"User request: {user_request}"
        ),
        chunk_token_threshold=1200,
        overlap_rate=0.0,
        apply_chunking=True,
        input_format="html",
        extra_args={"temperature": 0.0, "max_tokens": 1200},
    )
    crawl_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=80000,
        word_count_threshold=1,
        extraction_strategy=llm_strategy,
    )
    async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
        result = await crawler.arun(url=url, config=crawl_config)
    if not result.success:
        raise RuntimeError(result.error_message or "crawl4ai extraction failed.")
    extracted = _json_or_text(str(result.extracted_content or "").strip())
    if _is_empty_extraction(extracted):
        raise RuntimeError("crawl4ai LLM extraction returned empty JSON.")
    return extracted, len(str(result.markdown or "")), len(str(result.cleaned_html or ""))


def run_crawl4ai_performance_check(user_request: str, max_results: int = 5, progress_callback=None) -> Crawl4AIPerformanceResult:
    if not user_request.strip():
        raise ValueError("user_request is required.")
    started = time.perf_counter()
    timings: dict[str, float] = {}
    progress_messages: list[str] = []

    def report(message: str) -> None:
        progress_messages.append(message)
        if progress_callback:
            progress_callback(message)

    try:
        model_id = active_crawl4ai_model_id()
        extraction_mode = "llm"
        rate_limited = False
        fallback_reason = ""
        report(f"Crawl4AI LLM抽出モデル: {model_id}")
        report("ユーザー要望から検索クエリを作成しています。")
        step_started = time.perf_counter()
        try:
            search_query = build_search_query(user_request)
        except Exception as exc:
            if not is_rate_limit_error(exc):
                raise
            rate_limited = True
            extraction_mode = "plain_fallback"
            fallback_reason = f"Search query generation rate limit: {type(exc).__name__}: {exc}"
            search_query = user_request
            report("検索クエリ生成でOpenRouter free model制限に達したため、入力文をそのまま検索に使います。")
        timings["query_generation_sec"] = time.perf_counter() - step_started

        report(f"検索クエリを作成しました: {search_query}")
        step_started = time.perf_counter()
        candidate_urls = discover_urls_for_query(search_query, max_results=max_results)
        timings["search_sec"] = time.perf_counter() - step_started

        report(f"検索結果から候補URLを{len(candidate_urls)}件見つけました。")
        step_started = time.perf_counter()
        selected_url = select_best_url(user_request, search_query, candidate_urls)
        timings["url_selection_sec"] = time.perf_counter() - step_started

        report(f"最初に試すURLを選びました: {selected_url}")
        step_started = time.perf_counter()
        attempted_urls: list[str] = []
        extraction_errors: list[str] = []
        extracted_content = ""
        markdown_chars = 0
        cleaned_html_chars = 0
        ordered_urls = [selected_url] + [url for url in candidate_urls if url != selected_url]
        for url in ordered_urls:
            attempted_urls.append(url)
            report(f"crawl4aiでページを取得し、LLM抽出を試しています: {url}")
            try:
                if rate_limited:
                    report("すでにOpenRouter制限を検出しているため、通常抽出を実行します。")
                    extracted_content, markdown_chars, cleaned_html_chars = _run_async(crawl_plain_content(url))
                else:
                    extracted_content, markdown_chars, cleaned_html_chars = _run_async(
                        crawl_and_extract_with_llm(url, user_request, model_id=model_id)
                    )
                selected_url = url
                report("抽出に成功しました。結果を整形して表示します。")
                break
            except Exception as exc:
                extraction_errors.append(f"{url}: {type(exc).__name__}: {exc}")
                if is_rate_limit_error(exc):
                    rate_limited = True
                    extraction_mode = "plain_fallback"
                    fallback_reason = f"{type(exc).__name__}: {exc}"
                    report("OpenRouter free model制限に達したため、LLM抽出ではなく通常抽出に切り替えます。")
                    extracted_content, markdown_chars, cleaned_html_chars = _run_async(crawl_plain_content(url))
                    selected_url = url
                    break
                report(f"このURLでは抽出できませんでした。次の候補を試します: {type(exc).__name__}")
        else:
            raise RuntimeError("All candidate URLs failed.\n" + "\n".join(extraction_errors[:5]))
        timings["crawl_and_extract_sec"] = time.perf_counter() - step_started
        timings["total_sec"] = time.perf_counter() - started

        return Crawl4AIPerformanceResult(
            user_request=user_request,
            search_query=search_query,
            candidate_urls=candidate_urls,
            selected_url=selected_url,
            attempted_urls=attempted_urls,
            extracted_content=extracted_content,
            markdown_chars=markdown_chars,
            cleaned_html_chars=cleaned_html_chars,
            timings=timings,
            success=True,
            progress_messages=progress_messages,
            model_id=model_id,
            extraction_mode=extraction_mode,
            rate_limited=rate_limited,
            fallback_reason=fallback_reason,
        )
    except Exception as exc:
        timings["total_sec"] = time.perf_counter() - started
        report(f"処理を完了できませんでした: {type(exc).__name__}")
        return Crawl4AIPerformanceResult(
            user_request=user_request,
            search_query=locals().get("search_query", ""),
            candidate_urls=locals().get("candidate_urls", []),
            selected_url=locals().get("selected_url", ""),
            attempted_urls=locals().get("attempted_urls", []),
            extracted_content="",
            markdown_chars=0,
            cleaned_html_chars=0,
            timings=timings,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
            progress_messages=progress_messages,
            model_id=locals().get("model_id", ""),
            extraction_mode=locals().get("extraction_mode", "llm"),
            rate_limited=locals().get("rate_limited", False) or is_rate_limit_error(exc),
            fallback_reason=locals().get("fallback_reason", ""),
        )
