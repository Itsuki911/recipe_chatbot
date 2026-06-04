from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app import config
from app.llm import build_chat_llm, strip_hidden_reasoning


ADAPTIVE_OUTPUT_DIR = config.DATA_DIR / "adaptive_crawls"


@dataclass
class AdaptiveCrawlPage:
    url: str
    score: float
    title: str
    content: str


@dataclass
class AdaptiveCrawlResult:
    start_url: str
    query: str
    strategy: str
    confidence: float
    crawled_urls: list[str]
    relevant_pages: list[AdaptiveCrawlPage]
    synthesis: str
    architecture: dict[str, Any]
    output_dir: Path
    knowledge_base_path: Path
    result_path: Path
    timings: dict[str, float]
    success: bool
    error: str | None = None


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


def _safe_run_name(start_url: str, query: str) -> str:
    host = urlparse(start_url).netloc.replace(":", "_") or "site"
    query_slug = "".join(char if char.isalnum() else "-" for char in query.lower()).strip("-")
    query_slug = "-".join(part for part in query_slug.split("-") if part)[:48] or "research"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{host}-{query_slug}"


def _page_from_relevant(value: dict[str, Any]) -> AdaptiveCrawlPage:
    content = (
        value.get("content")
        or value.get("markdown")
        or value.get("text")
        or value.get("summary")
        or ""
    )
    title = value.get("title") or value.get("url") or "Untitled"
    return AdaptiveCrawlPage(
        url=str(value.get("url") or ""),
        score=float(value.get("score") or value.get("relevance") or 0.0),
        title=str(title),
        content=str(content).strip(),
    )


def _compact_pages_for_llm(pages: list[AdaptiveCrawlPage], max_chars_per_page: int = 1800) -> str:
    blocks: list[str] = []
    for index, page in enumerate(pages, start=1):
        content = page.content[:max_chars_per_page]
        blocks.append(
            f"Page {index}\n"
            f"URL: {page.url}\n"
            f"Score: {page.score:.3f}\n"
            f"Title: {page.title}\n"
            f"Content excerpt:\n{content}"
        )
    return "\n\n---\n\n".join(blocks)


def _build_architecture(
    *,
    start_url: str,
    query: str,
    strategy: str,
    max_pages: int,
    max_depth: int,
    top_k_links: int,
    confidence_threshold: float,
) -> dict[str, Any]:
    return {
        "goal": "Adaptive site research with crawl4ai, internal URL expansion, text extraction, and LLM synthesis.",
        "inputs": {
            "start_url": start_url,
            "query": query,
            "site_scope": "same-site links discovered by crawl4ai AdaptiveCrawler",
        },
        "pipeline": [
            "Seed crawl from start_url.",
            "Extract page text and link previews with crawl4ai.",
            "Rank internal links by query relevance, novelty, and information gain.",
            "Follow top internal URLs until confidence, depth, or page limits stop the crawl.",
            "Collect relevant content into a local knowledge base JSONL file.",
            "Ask the configured LLM to synthesize findings, gaps, and next investigation targets.",
        ],
        "adaptive_controls": {
            "strategy": strategy,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "top_k_links": top_k_links,
            "confidence_threshold": confidence_threshold,
        },
        "outputs": {
            "knowledge_base_jsonl": "Raw adaptive crawl knowledge base.",
            "result_json": "Crawl metadata, relevant pages, synthesis, and this architecture object.",
        },
    }


def synthesize_adaptive_findings(
    *,
    query: str,
    start_url: str,
    confidence: float,
    pages: list[AdaptiveCrawlPage],
) -> str:
    if not pages:
        return "No relevant pages were collected, so no synthesis could be generated."

    llm = build_chat_llm(config.STRUCTURED_LLM_BACKEND, temperature=0.0)
    prompt = (
        "You are a senior web research agent. Use the crawled pages to answer the research query. "
        "Explain what was found, cite URLs inline, identify gaps or uncertainty, and propose the next internal URLs "
        "or subtopics that should be explored if the investigation continues. Do not invent facts.\n\n"
        f"Start URL: {start_url}\n"
        f"Research query: {query}\n"
        f"Adaptive crawler confidence: {confidence:.3f}\n\n"
        f"Crawled relevant pages:\n{_compact_pages_for_llm(pages)}"
    )
    response = llm.invoke(prompt)
    text = response.content if hasattr(response, "content") else response
    return strip_hidden_reasoning(str(text))


async def _run_adaptive_crawl_async(
    *,
    start_url: str,
    query: str,
    max_pages: int,
    max_depth: int,
    top_k_links: int,
    confidence_threshold: float,
    strategy: str,
    top_k_content: int,
    save_state: bool,
) -> AdaptiveCrawlResult:
    from crawl4ai import AdaptiveConfig, AdaptiveCrawler, AsyncWebCrawler, BrowserConfig

    started = time.perf_counter()
    run_dir = ADAPTIVE_OUTPUT_DIR / _safe_run_name(start_url, query)
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "adaptive_state.json"
    knowledge_base_path = run_dir / "knowledge_base.jsonl"
    result_path = run_dir / "result.json"

    architecture = _build_architecture(
        start_url=start_url,
        query=query,
        strategy=strategy,
        max_pages=max_pages,
        max_depth=max_depth,
        top_k_links=top_k_links,
        confidence_threshold=confidence_threshold,
    )
    adaptive_config = AdaptiveConfig(
        confidence_threshold=confidence_threshold,
        max_pages=max_pages,
        max_depth=max_depth,
        top_k_links=top_k_links,
        strategy=strategy,
        save_state=save_state,
        state_path=str(state_path),
    )

    async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
        adaptive = AdaptiveCrawler(crawler, adaptive_config)
        state = await adaptive.digest(start_url=start_url, query=query)
        relevant_pages = [
            _page_from_relevant(page)
            for page in adaptive.get_relevant_content(top_k=top_k_content)
        ]
        adaptive.export_knowledge_base(str(knowledge_base_path))
        confidence = float(getattr(adaptive, "confidence", 0.0) or 0.0)

    crawled_urls = [str(url) for url in getattr(state, "crawled_urls", [])]
    synthesis = synthesize_adaptive_findings(
        query=query,
        start_url=start_url,
        confidence=confidence,
        pages=relevant_pages,
    )
    timings = {"total_sec": time.perf_counter() - started}
    result = AdaptiveCrawlResult(
        start_url=start_url,
        query=query,
        strategy=strategy,
        confidence=confidence,
        crawled_urls=crawled_urls,
        relevant_pages=relevant_pages,
        synthesis=synthesis,
        architecture=architecture,
        output_dir=run_dir,
        knowledge_base_path=knowledge_base_path,
        result_path=result_path,
        timings=timings,
        success=True,
    )
    result_path.write_text(
        json.dumps(_result_to_jsonable(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _result_to_jsonable(result: AdaptiveCrawlResult) -> dict[str, Any]:
    data = asdict(result)
    data["output_dir"] = str(result.output_dir)
    data["knowledge_base_path"] = str(result.knowledge_base_path)
    data["result_path"] = str(result.result_path)
    return data


def run_adaptive_site_research(
    *,
    start_url: str,
    query: str,
    max_pages: int = 12,
    max_depth: int = 3,
    top_k_links: int = 3,
    confidence_threshold: float = 0.75,
    strategy: str = "statistical",
    top_k_content: int = 6,
    save_state: bool = True,
) -> AdaptiveCrawlResult:
    if not start_url.strip():
        raise ValueError("start_url is required.")
    if not query.strip():
        raise ValueError("query is required.")
    if strategy not in {"statistical", "embedding"}:
        raise ValueError("strategy must be 'statistical' or 'embedding'.")

    return _run_async(
        _run_adaptive_crawl_async(
            start_url=start_url.strip(),
            query=query.strip(),
            max_pages=max_pages,
            max_depth=max_depth,
            top_k_links=top_k_links,
            confidence_threshold=confidence_threshold,
            strategy=strategy,
            top_k_content=top_k_content,
            save_state=save_state,
        )
    )


def adaptive_architecture_preview(
    *,
    start_url: str = "https://www.justonecookbook.com/",
    query: str = "omurice recipe techniques and variations",
    strategy: str = "statistical",
    max_pages: int = 12,
    max_depth: int = 3,
    top_k_links: int = 3,
    confidence_threshold: float = 0.75,
) -> dict[str, Any]:
    return _build_architecture(
        start_url=start_url,
        query=query,
        strategy=strategy,
        max_pages=max_pages,
        max_depth=max_depth,
        top_k_links=top_k_links,
        confidence_threshold=confidence_threshold,
    )
