from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TypedDict
from urllib.parse import urlparse

from app import config
from app.scraper import SavedPage, discover_recipe_links_from_search, save_many_recipe_pages


@dataclass
class DeepAgentResult:
    # UIやログで、エージェントが何を検索・選択・保存したかを確認するための結果です。
    query: str
    search_queries: list[str]
    candidate_urls: list[str]
    selected_urls: list[str]
    saved_pages: list[SavedPage]
    notes: str


class RecipeCollectionState(TypedDict):
    # LangGraphの各nodeが読み書きする共有状態です。
    query: str
    max_pages: int
    search_queries: list[str]
    candidate_urls: list[str]
    selected_urls: list[str]
    saved_pages: list[SavedPage]
    notes: str
    errors: list[str]


def _parse_json_array(text: str) -> list[str]:
    # Geminiの出力が ```json ... ``` で包まれても扱えるように、JSON配列部分だけを探します。
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _same_site_recipe_url(url: str) -> bool:
    # Just One Cookbook内の、空でないパスを持つURLだけを保存候補にします。
    parsed = urlparse(url)
    expected = urlparse(config.JOC_START_URL)
    return parsed.netloc == expected.netloc and bool(parsed.path.strip("/"))


def _dedupe_urls(urls: list[str], max_items: int = 20) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        clean_url = url.split("#")[0]
        if clean_url in seen or not _same_site_recipe_url(clean_url):
            continue
        seen.add(clean_url)
        result.append(clean_url)
        if len(result) >= max_items:
            break
    return result


def _build_llm():
    # LangChainのChatGoogleGenerativeAIを使います。RAG回答用のLLMとは独立した収集計画用LLMです。
    if not config.GOOGLE_API_KEY:
        raise RuntimeError("LangGraph Deep Agent requires GOOGLE_API_KEY in .env.")

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        temperature=0.0,
        google_api_key=config.GOOGLE_API_KEY,
    )


def plan_search_queries(state: RecipeCollectionState) -> dict[str, list[str]]:
    # Node 1: ユーザーの入力から、Just One Cookbook検索に向いた英語クエリを作ります。
    llm = _build_llm()
    response = llm.invoke(
        [
            (
                "system",
                "Create concise search queries for Just One Cookbook recipe collection. "
                "Return only a JSON array of strings. Do not include commentary.",
            ),
            (
                "human",
                f"Target recipe/theme: {state['query']}\n"
                f"Need up to {state['max_pages']} useful recipe pages.",
            ),
        ]
    )
    planned = _parse_json_array(str(response.content))
    if state["query"] not in planned:
        planned.insert(0, state["query"])
    return {"search_queries": planned[: max(1, state["max_pages"])]}


def search_candidate_urls(state: RecipeCollectionState) -> dict[str, list[str]]:
    # Node 2: 各検索クエリでJust One Cookbook内検索を実行し、候補URLを集めます。
    urls: list[str] = []
    errors = list(state.get("errors", []))
    for search_query in state["search_queries"]:
        try:
            urls.extend(discover_recipe_links_from_search(search_query, max_results=state["max_pages"] * 2))
        except Exception as exc:
            errors.append(f"{search_query}: {type(exc).__name__}: {exc}")
    return {"candidate_urls": _dedupe_urls(urls), "errors": errors}


def select_recipe_urls(state: RecipeCollectionState) -> dict[str, list[str] | str]:
    # Node 3: 候補URLの中から、RAGに保存する価値が高いURLをLLMに選ばせます。
    candidates = state["candidate_urls"]
    if not candidates:
        return {"selected_urls": [], "notes": "No candidate URLs were found."}

    llm = _build_llm()
    numbered = "\n".join(f"{index + 1}. {url}" for index, url in enumerate(candidates))
    response = llm.invoke(
        [
            (
                "system",
                "Choose the most relevant Just One Cookbook recipe URLs for a local RAG chatbot. "
                "Return only a JSON array of URLs from the candidate list. Do not invent URLs.",
            ),
            (
                "human",
                f"User target: {state['query']}\n"
                f"Max pages: {state['max_pages']}\n"
                f"Candidate URLs:\n{numbered}",
            ),
        ]
    )
    selected = [url for url in _parse_json_array(str(response.content)) if url in candidates]
    if not selected:
        selected = candidates[: state["max_pages"]]
    return {
        "selected_urls": selected[: state["max_pages"]],
        "notes": f"Selected {min(len(selected), state['max_pages'])} URL(s) from {len(candidates)} candidate(s).",
    }


def save_selected_pages(state: RecipeCollectionState) -> dict[str, list[SavedPage] | list[str]]:
    # Node 4: 選ばれたURLをdata/joc_pagesへ保存します。保存後は既存RAGのindex再構築対象になります。
    errors = list(state.get("errors", []))
    selected_urls = state["selected_urls"]
    if not selected_urls:
        if errors:
            raise RuntimeError("No URLs were selected.\n" + "\n".join(errors[:5]))
        raise RuntimeError("No URLs were selected.")
    try:
        saved_pages = save_many_recipe_pages(selected_urls, max_pages=state["max_pages"])
    except Exception as exc:
        errors.append(f"save_selected_pages: {type(exc).__name__}: {exc}")
        raise RuntimeError("Selected URLs could not be saved.\n" + "\n".join(errors[:5])) from exc
    return {"saved_pages": saved_pages, "errors": errors}


def build_recipe_collection_graph():
    # 公式ドキュメントのStateGraphパターンに沿って、nodeとedgeを定義してcompileします。
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("Install langgraph to use the LangChain/LangGraph Deep Agent.") from exc

    builder = StateGraph(RecipeCollectionState)
    builder.add_node("plan_search_queries", plan_search_queries)
    builder.add_node("search_candidate_urls", search_candidate_urls)
    builder.add_node("select_recipe_urls", select_recipe_urls)
    builder.add_node("save_selected_pages", save_selected_pages)
    builder.add_edge(START, "plan_search_queries")
    builder.add_edge("plan_search_queries", "search_candidate_urls")
    builder.add_edge("search_candidate_urls", "select_recipe_urls")
    builder.add_edge("select_recipe_urls", "save_selected_pages")
    builder.add_edge("save_selected_pages", END)
    return builder.compile()


def run_deep_agent_recipe_collection(query: str, max_pages: int = 3) -> list[SavedPage]:
    result = run_deep_agent_recipe_collection_with_details(query=query, max_pages=max_pages)
    return result.saved_pages


def run_deep_agent_recipe_collection_with_details(query: str, max_pages: int = 3) -> DeepAgentResult:
    if not query.strip():
        raise ValueError("query is required.")

    graph = build_recipe_collection_graph()
    state = graph.invoke(
        {
            "query": query.strip(),
            "max_pages": max_pages,
            "search_queries": [],
            "candidate_urls": [],
            "selected_urls": [],
            "saved_pages": [],
            "notes": "",
            "errors": [],
        }
    )
    return DeepAgentResult(
        query=state["query"],
        search_queries=state["search_queries"],
        candidate_urls=state["candidate_urls"],
        selected_urls=state["selected_urls"],
        saved_pages=state["saved_pages"],
        notes=state["notes"],
    )
