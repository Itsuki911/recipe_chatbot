from __future__ import annotations

import re
import sys
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
    app_config = None

BASE_DIR = Path(__file__).resolve().parent.parent
JOC_START_URL = getattr(app_config, "JOC_START_URL", "https://www.justonecookbook.com/")
LOCAL_RECIPE_DIR = getattr(app_config, "LOCAL_RECIPE_DIR", BASE_DIR / "data" / "joc_pages")
GOOGLE_API_KEY = getattr(app_config, "GOOGLE_API_KEY", None)
GEMINI_MODEL = getattr(app_config, "GEMINI_MODEL", "gemini-2.5-flash")


@dataclass
class SavedPage:
    url: str
    path: Path
    title: str
    text_chars: int


def _safe_slug(value: str) -> str:
    parsed = urlparse(value)
    candidate = parsed.path.strip("/").split("/")[-1] or parsed.netloc or "recipe-page"
    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "-", candidate).strip("-").lower()
    return candidate or "recipe-page"


def _extract_recipe_text(html: str) -> tuple[str, str]:
    soup = bs4.BeautifulSoup(html, "html.parser")
    title_node = soup.find(class_="entry-title") or soup.find("h1") or soup.find("title")
    title = title_node.get_text(" ", strip=True) if title_node else "Untitled recipe"
    content = soup.select_one(".entry-content") or soup.select_one(".wprm-recipe-container") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", content.get_text("\n", strip=True)).strip()
    return title, text


def fetch_recipe_page(url: str, timeout: int = 30) -> tuple[str, str, str]:
    response = requests.get(url, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    title, text = _extract_recipe_text(response.text)
    if len(text) < 500:
        raise ValueError(f"Recipe text is too short to index safely ({len(text)} chars).")
    return response.text, title, text


def save_recipe_page_from_url(url: str, output_dir: Path = LOCAL_RECIPE_DIR) -> SavedPage:
    output_dir.mkdir(parents=True, exist_ok=True)
    html, title, text = fetch_recipe_page(url)
    slug = _safe_slug(url)
    html_path = output_dir / f"{slug}.html"
    text_path = output_dir / f"{slug}.txt"
    html_path.write_text(html, encoding="utf-8")
    text_path.write_text(f"{title}\n\nSource: {url}\n\n{text}\n", encoding="utf-8")
    return SavedPage(url=url, path=text_path, title=title, text_chars=len(text))


def discover_recipe_links_from_search(query: str, max_results: int = 5) -> list[str]:
    search_url = f"{JOC_START_URL.rstrip('/')}/?s={quote_plus(query)}"
    response = requests.get(search_url, headers=_headers(), timeout=30)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(search_url, anchor["href"]).split("#")[0]
        parsed = urlparse(href)
        if parsed.netloc != urlparse(JOC_START_URL).netloc:
            continue
        if href in seen or not parsed.path.strip("/"):
            continue
        seen.add(href)
        links.append(href)
        if len(links) >= max_results:
            break
    return links


def save_many_recipe_pages(urls: Iterable[str], max_pages: int = 5) -> list[SavedPage]:
    saved: list[SavedPage] = []
    errors: list[str] = []
    for url in list(urls)[:max_pages]:
        try:
            saved.append(save_recipe_page_from_url(url))
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    if not saved and errors:
        raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
    return saved


def run_deep_agent_recipe_collection(query: str, max_pages: int = 3) -> list[SavedPage]:
    """Use LangChain Deep Agents when available, then save the selected recipe pages locally."""
    if sys.version_info < (3, 11):
        raise RuntimeError(
            "LangChain Deep Agents requires Python 3.11 or newer. "
            f"Current Python is {sys.version_info.major}.{sys.version_info.minor}. "
            "Use the URL保存 feature on Python 3.10, or create a Python 3.11 environment for Deep Agent collection."
        )
    if not GOOGLE_API_KEY:
        raise RuntimeError("Deep Agent collection requires GOOGLE_API_KEY in .env.")

    try:
        from deepagents import create_deep_agent
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise RuntimeError("Install deepagents and langchain-google-genai to use Deep Agent collection.") from exc

    found_urls: list[str] = []

    def search_just_one_cookbook(search_query: str, limit: int = max_pages) -> list[str]:
        """Search Just One Cookbook for candidate recipe URLs."""
        urls = discover_recipe_links_from_search(search_query, max_results=limit)
        found_urls.extend(url for url in urls if url not in found_urls)
        return urls

    def save_just_one_cookbook_url(url: str) -> str:
        """Save a Just One Cookbook recipe URL into the local RAG data folder."""
        saved = save_recipe_page_from_url(url)
        if saved.url not in found_urls:
            found_urls.append(saved.url)
        return f"Saved {saved.title} to {saved.path}"

    model = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0.0, google_api_key=GOOGLE_API_KEY)
    agent = create_deep_agent(
        model=model,
        tools=[search_just_one_cookbook, save_just_one_cookbook_url],
        system_prompt=(
            "You collect Japanese recipe pages for a local RAG chatbot. "
            "Search Just One Cookbook for the user's target recipe, choose the most relevant URLs, "
            "and save up to the requested number of pages. Do not invent URLs."
        ),
    )
    agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Find and save up to {max_pages} Just One Cookbook pages relevant to: {query}. "
                        "Use the provided tools and report what you saved."
                    ),
                }
            ]
        },
        config={"configurable": {"thread_id": f"recipe-collection-{_safe_slug(query)}"}},
    )

    saved_paths = {path.stem for path in LOCAL_RECIPE_DIR.glob("*.txt")}
    saved_urls = [url for url in found_urls if _safe_slug(url) in saved_paths]
    if saved_urls:
        return [
            SavedPage(
                url=url,
                path=LOCAL_RECIPE_DIR / f"{_safe_slug(url)}.txt",
                title=_safe_slug(url),
                text_chars=(LOCAL_RECIPE_DIR / f"{_safe_slug(url)}.txt").stat().st_size,
            )
            for url in saved_urls[:max_pages]
        ]

    fallback_urls = discover_recipe_links_from_search(query, max_results=max_pages)
    return save_many_recipe_pages(fallback_urls, max_pages=max_pages)
