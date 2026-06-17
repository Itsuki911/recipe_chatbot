from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import bs4
import requests

from app import config
from app.llm import build_chat_llm, strip_hidden_reasoning
from app.rag_chatbot import _headers
from app.scraper import SavedPage


WEB_RECIPE_REFERENCE_DIR = config.WEB_RECIPE_REFERENCE_DIR


@dataclass
class DeepAgentResult:
    # UIやログで、Agentic Crawlerが何を検索・選択・保存したかを確認するための結果です。
    query: str
    search_queries: list[str]
    candidate_urls: list[str]
    selected_urls: list[str]
    saved_pages: list[SavedPage]
    notes: str


def _run_async(coro):
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


def _safe_slug(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.netloc.replace(":", "-")
    path = parsed.path.strip("/").replace("/", "-")
    candidate = f"{host}-{path}" if path else host
    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "-", candidate).strip("-").lower()
    return candidate[:90] or "web-reference"


def _json_array_or_fallback(text: str, fallback: list[str]) -> list[str]:
    text = strip_hidden_reasoning(text)
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return fallback
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback
    values = [str(item).strip() for item in parsed if str(item).strip()]
    return values or fallback


def _build_llm():
    return build_chat_llm(config.DEEP_AGENT_LLM_BACKEND, temperature=0.0)


def plan_search_queries(query: str, max_pages: int) -> list[str]:
    # LLMを「調査方針を決める脳」として使い、Web検索に投入するクエリを作ります。
    llm = _build_llm()
    response = llm.invoke(
        [
            (
                "system",
                "You plan web research for recipe and cooking references. "
                "Return only a JSON array of concise web search queries. "
                "Do not restrict results to a single website unless the user asks for it.",
            ),
            (
                "human",
                f"Research target: {query}\n"
                f"Need enough references to save up to {max_pages} useful pages.",
            ),
        ]
    )
    fallback = [f"{query} recipe", f"{query} cooking guide", f"{query} ingredients technique"]
    return _json_array_or_fallback(str(response.content), fallback)[: max(2, min(5, max_pages + 1))]


def plan_crawl_keywords(query: str, search_queries: list[str]) -> list[str]:
    llm = _build_llm()
    response = llm.invoke(
        [
            (
                "system",
                "Create relevance keywords for a crawl4ai BestFirstCrawlingStrategy. "
                "Return only a JSON array of short keywords or phrases.",
            ),
            (
                "human",
                f"Research target: {query}\nSearch queries:\n"
                + "\n".join(f"- {item}" for item in search_queries),
            ),
        ]
    )
    fallback = re.findall(r"[a-zA-Z0-9]+", query.lower())
    return _json_array_or_fallback(str(response.content), fallback)[:12]


def _extract_duckduckgo_url(href: str) -> str:
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return unquote(params["uddg"][0])
    return href


def discover_web_urls(search_query: str, max_results: int = 6) -> list[str]:
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
        url = _extract_duckduckgo_url(href).split("#")[0]
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


def select_seed_urls(query: str, candidate_urls: list[str], max_seeds: int = 3) -> list[str]:
    if not candidate_urls:
        return []
    llm = _build_llm()
    numbered = "\n".join(f"{index + 1}. {url}" for index, url in enumerate(candidate_urls))
    response = llm.invoke(
        [
            (
                "system",
                "Choose the best seed URLs for an agentic crawl4ai web investigation. "
                "Prefer pages likely to contain recipe, cooking, ingredient, or technique details. "
                "Return only a JSON array of URLs copied exactly from the candidate list.",
            ),
            ("human", f"Research target: {query}\nCandidate URLs:\n{numbered}"),
        ]
    )
    selected = [url for url in _json_array_or_fallback(str(response.content), []) if url in candidate_urls]
    return (selected or candidate_urls)[:max_seeds]


def _extract_text_from_result(result: Any) -> str:
    markdown = str(getattr(result, "markdown", "") or "").strip()
    if markdown:
        return re.sub(r"\n{3,}", "\n\n", markdown).strip()
    cleaned_html = str(getattr(result, "cleaned_html", "") or "").strip()
    return re.sub(r"\n{3,}", "\n\n", bs4.BeautifulSoup(cleaned_html, "html.parser").get_text("\n", strip=True)).strip()


def _extract_html_from_result(result: Any) -> str:
    return str(getattr(result, "cleaned_html", "") or getattr(result, "html", "") or "").strip()


def _title_from_text(text: str, url: str) -> str:
    for line in text.splitlines():
        stripped = line.strip("# ").strip()
        if len(stripped) >= 8:
            return stripped[:120]
    parsed = urlparse(url)
    return (parsed.path.strip("/").split("/")[-1] or parsed.netloc or "Web reference").replace("-", " ").title()


def _save_reference_page(url: str, html: str, text: str, output_dir: Path = WEB_RECIPE_REFERENCE_DIR) -> SavedPage:
    output_dir.mkdir(parents=True, exist_ok=True)
    title = _title_from_text(text, url)
    slug = _safe_slug(url)
    html_path = output_dir / f"{slug}.html"
    text_path = output_dir / f"{slug}.txt"
    html_path.write_text(html or f"<pre>{text}</pre>", encoding="utf-8")
    text_path.write_text(f"{title}\n\nSource: {url}\n\n{text}\n", encoding="utf-8")
    from app.gcs_storage import is_enabled, upload_text

    if is_enabled():
        upload_text(
            f"web_recipe_reference/{slug}.html",
            html or f"<pre>{text}</pre>",
            content_type="text/html; charset=utf-8",
        )
        upload_text(
            f"web_recipe_reference/{slug}.txt",
            f"{title}\n\nSource: {url}\n\n{text}\n",
        )
    return SavedPage(url=url, path=text_path, title=title, text_chars=len(text))


def _fetch_reference_page_fallback(url: str) -> SavedPage | None:
    try:
        response = requests.get(url, headers=_headers(), timeout=30)
        response.raise_for_status()
    except Exception:
        return None

    html = response.text
    soup = bs4.BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    content = soup.select_one("article") or soup.select_one("main") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", content.get_text("\n", strip=True)).strip()
    if len(text) < 500:
        return None
    return _save_reference_page(url, html, text)


async def _agentic_crawl_seed(
    *,
    seed_url: str,
    query: str,
    keywords: list[str],
    max_pages: int,
    max_depth: int,
) -> list[SavedPage]:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
    from crawl4ai.deep_crawling.filters import ContentTypeFilter, DomainFilter, FilterChain
    from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

    domain = urlparse(seed_url).netloc
    filter_chain = FilterChain(
        [
            DomainFilter(allowed_domains=[domain]),
            ContentTypeFilter(allowed_types=["text/html"]),
        ]
    )
    scorer = KeywordRelevanceScorer(keywords=keywords or [query], weight=0.9)
    crawl_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        deep_crawl_strategy=BestFirstCrawlingStrategy(
            max_depth=max_depth,
            include_external=False,
            max_pages=max_pages,
            filter_chain=filter_chain,
            url_scorer=scorer,
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        stream=True,
        verbose=False,
    )

    saved_pages: list[SavedPage] = []
    async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
        async for result in await crawler.arun(seed_url, config=crawl_config):
            if not getattr(result, "success", True):
                continue
            url = str(getattr(result, "url", "") or seed_url)
            text = _extract_text_from_result(result)
            if len(text) < 500:
                continue
            html = _extract_html_from_result(result)
            saved_pages.append(_save_reference_page(url, html, text))
            if len(saved_pages) >= max_pages:
                break
    return saved_pages


async def _run_agentic_crawler(query: str, max_pages: int) -> DeepAgentResult:
    search_queries = plan_search_queries(query, max_pages)
    keywords = plan_crawl_keywords(query, search_queries)
    candidate_urls: list[str] = []
    seen: set[str] = set()
    for search_query in search_queries:
        try:
            for url in discover_web_urls(search_query, max_results=6):
                if url not in seen:
                    seen.add(url)
                    candidate_urls.append(url)
        except Exception:
            continue

    selected_urls = select_seed_urls(query, candidate_urls, max_seeds=min(3, max_pages))
    if not selected_urls:
        raise RuntimeError("Agentic Crawler could not discover seed URLs for the query.")

    saved_pages: list[SavedPage] = []
    errors: list[str] = []
    per_seed_limit = max(1, max_pages)
    for seed_url in selected_urls:
        try:
            for page in await _agentic_crawl_seed(
                seed_url=seed_url,
                query=query,
                keywords=keywords,
                max_pages=per_seed_limit,
                max_depth=2,
            ):
                if page.url not in {saved.url for saved in saved_pages}:
                    saved_pages.append(page)
                if len(saved_pages) >= max_pages:
                    break
        except Exception as exc:
            errors.append(f"{seed_url}: {type(exc).__name__}: {exc}")
        if len(saved_pages) >= max_pages:
            break

    if not saved_pages:
        fallback_urls: list[str] = []
        for url in [*selected_urls, *candidate_urls]:
            if url not in fallback_urls:
                fallback_urls.append(url)
        for url in fallback_urls:
            page = _fetch_reference_page_fallback(url)
            if page and page.url not in {saved.url for saved in saved_pages}:
                saved_pages.append(page)
            if len(saved_pages) >= max_pages:
                break

    if not saved_pages:
        detail = "\n".join(errors[:5]) if errors else "No crawl results had enough text to save."
        raise RuntimeError(f"Agentic Crawler did not save any pages.\n{detail}")

    notes = (
        f"Saved {len(saved_pages)} page(s) to {WEB_RECIPE_REFERENCE_DIR}. "
        f"Keywords: {', '.join(keywords[:8])}"
    )
    return DeepAgentResult(
        query=query,
        search_queries=search_queries,
        candidate_urls=candidate_urls,
        selected_urls=selected_urls,
        saved_pages=saved_pages,
        notes=notes,
    )


def run_deep_agent_recipe_collection(query: str, max_pages: int = 3) -> list[SavedPage]:
    result = run_deep_agent_recipe_collection_with_details(query=query, max_pages=max_pages)
    return result.saved_pages


def run_deep_agent_recipe_collection_with_details(query: str, max_pages: int = 3) -> DeepAgentResult:
    if not query.strip():
        raise ValueError("query is required.")
    return _run_async(_run_agentic_crawler(query.strip(), max_pages=max_pages))
