from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urljoin, urlparse

import bs4
import requests

from app.rag_chatbot import _headers

try:
    from app import config as app_config
except ImportError:
    # config importが壊れていても、最低限のfallback値で動くようにします。
    app_config = None

# RAG用に保存するレシピページの取得先と保存先です。
BASE_DIR = Path(__file__).resolve().parent.parent
JOC_START_URL = getattr(app_config, "JOC_START_URL", "https://www.justonecookbook.com/")
LOCAL_RECIPE_DIR = getattr(app_config, "LOCAL_RECIPE_DIR", BASE_DIR / "data" / "joc_pages")


@dataclass
class SavedPage:
    # UIへ「どのURLをどのファイルに保存したか」を返すための小さなデータ入れ物です。
    url: str
    path: Path
    title: str
    text_chars: int


def _safe_slug(value: str) -> str:
    # URLをファイル名に使える安全な文字列へ変換します。
    parsed = urlparse(value)
    candidate = parsed.path.strip("/").split("/")[-1] or parsed.netloc or "recipe-page"
    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "-", candidate).strip("-").lower()
    return candidate or "recipe-page"


def is_likely_recipe_page_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return False
    parts = [part for part in path.split("/") if part]
    if len(parts) != 1:
        return False
    excluded = {
        "about",
        "category",
        "categories",
        "contact",
        "privacy-policy",
        "recipe-index",
        "recipes",
        "search",
        "shop",
        "tag",
        "tags",
    }
    return parts[0].lower() not in excluded


def _extract_recipe_text(html: str) -> tuple[str, str]:
    # HTMLからタイトルと本文を取り出します。CSS selectorはサイト構造に合わせています。
    soup = bs4.BeautifulSoup(html, "html.parser")
    title_node = soup.find(class_="entry-title") or soup.find("h1") or soup.find("title")
    title = title_node.get_text(" ", strip=True) if title_node else "Untitled recipe"
    content = soup.select_one(".entry-content") or soup.select_one(".wprm-recipe-container") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", content.get_text("\n", strip=True)).strip()
    return title, text


def _run_async(coro):
    # Streamlitなど、既にevent loopがある環境でもasync関数を同期的に呼べるようにします。
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


def _title_from_markdown(markdown: str, url: str) -> str:
    # crawl4aiはMarkdownを返すため、最初の見出しをタイトルとして使います。
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or "Untitled recipe"
    return _safe_slug(url).replace("-", " ").title()


async def crawl_recipe_page(url: str) -> tuple[str, str, str]:
    # crawl4ai公式例に沿って、AsyncWebCrawlerでURLからLLM向けMarkdownを抽出します。
    try:
        from crawl4ai import AsyncWebCrawler
        from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    except ImportError as exc:
        raise RuntimeError("Install crawl4ai to collect recipe pages with the Deep Agent.") from exc

    browser_config = BrowserConfig(headless=True)
    run_config = CrawlerRunConfig(
        css_selector=".entry-title, .entry-content, .wprm-recipe-container",
    )
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not getattr(result, "success", True):
        raise RuntimeError(getattr(result, "error_message", "crawl4ai failed to crawl the page."))

    markdown = str(getattr(result, "markdown", "") or "").strip()
    cleaned_html = str(getattr(result, "cleaned_html", "") or "").strip()
    title = _title_from_markdown(markdown, url)
    if cleaned_html:
        html_title, _ = _extract_recipe_text(cleaned_html)
        if html_title and html_title != "Untitled recipe":
            title = html_title

    text = markdown or re.sub(r"\n{3,}", "\n\n", bs4.BeautifulSoup(cleaned_html, "html.parser").get_text("\n", strip=True))
    text = text.strip()
    if len(text) < 500:
        raise ValueError(f"Recipe text is too short to index safely ({len(text)} chars).")
    return cleaned_html or markdown, title, text


def fetch_recipe_page(url: str, timeout: int = 30) -> tuple[str, str, str]:
    # timeoutは後方互換のために残しています。実際の取得はcrawl4aiが管理します。
    return _run_async(crawl_recipe_page(url))


def save_recipe_page_from_url(url: str, output_dir: Path = LOCAL_RECIPE_DIR) -> SavedPage:
    # RAG index再構築時に使えるよう、crawl4aiの抽出Markdownとテキストを保存します。
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_content, title, text = fetch_recipe_page(url)
    slug = _safe_slug(url)
    markdown_path = output_dir / f"{slug}.md"
    text_path = output_dir / f"{slug}.txt"
    markdown_path.write_text(f"# {title}\n\nSource: {url}\n\n{extracted_content}\n", encoding="utf-8")
    text_path.write_text(f"{title}\n\nSource: {url}\n\n{text}\n", encoding="utf-8")
    from app.gcs_storage import is_enabled, upload_text

    if is_enabled():
        upload_text(f"joc_pages/{slug}.md", f"# {title}\n\nSource: {url}\n\n{extracted_content}\n")
        upload_text(f"joc_pages/{slug}.txt", f"{title}\n\nSource: {url}\n\n{text}\n")
    return SavedPage(url=url, path=text_path, title=title, text_chars=len(text))


def discover_recipe_links_from_search(query: str, max_results: int = 5) -> list[str]:
    # Just One Cookbook内検索を使い、ユーザーのキーワードに近いページURLを集めます。
    search_url = f"{JOC_START_URL.rstrip('/')}/?s={quote_plus(query)}"
    response = requests.get(search_url, headers=_headers(), timeout=30)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        # 検索結果ページ内のリンクから、同じサイト内のURLだけを候補にします。
        href = urljoin(search_url, anchor["href"]).split("#")[0]
        parsed = urlparse(href)
        if parsed.netloc != urlparse(JOC_START_URL).netloc:
            continue
        if href in seen or not is_likely_recipe_page_url(href):
            continue
        seen.add(href)
        links.append(href)
        if len(links) >= max_results:
            break
    return links


def save_many_recipe_pages(urls: Iterable[str], max_pages: int = 5) -> list[SavedPage]:
    # 複数URLを順に保存します。失敗したURLがあっても、他のURL保存は続けます。
    saved: list[SavedPage] = []
    errors: list[str] = []
    for url in list(urls):
        if len(saved) >= max_pages:
            break
        try:
            saved.append(save_recipe_page_from_url(url))
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    if not saved and errors:
        raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
    return saved


def run_deep_agent_recipe_collection(query: str, max_pages: int = 3) -> list[SavedPage]:
    """Collect recipe pages with the LangChain/LangGraph Deep Agent."""
    # 後方互換用の薄いwrapperです。古いdeepagentsパッケージには依存しません。
    from app.deep_agent import run_deep_agent_recipe_collection as run_langgraph_deep_agent

    return run_langgraph_deep_agent(query=query, max_pages=max_pages)
