from __future__ import annotations

import os
import base64
import time
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

try:
    from app.config import (
        DEEP_AGENT_LLM_BACKEND,
        LOCAL_RECIPE_DIR,
        OPENROUTER_MODEL,
        VECTOR_INDEX_DIR,
        WEB_RECIPE_REFERENCE_DIR,
        CLOUD_RUN_DEEP_AGENT_JOB,
        GCS_BUCKET,
    )
except ImportError:
    # config.pyのimport前に壊れても、Streamlit画面とログ出力を最低限続けるためのfallbackです。
    fallback_data_dir = Path(__file__).resolve().parent / "data"
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
    DEEP_AGENT_LLM_BACKEND = os.getenv("DEEP_AGENT_LLM_BACKEND", os.getenv("MAIN_LLM_BACKEND", "openrouter")).lower()
    VECTOR_INDEX_DIR = fallback_data_dir / "turbovec_index"
    LOCAL_RECIPE_DIR = fallback_data_dir / "joc_pages"
    WEB_RECIPE_REFERENCE_DIR = fallback_data_dir / "web_recipe_reference"
    CLOUD_RUN_DEEP_AGENT_JOB = os.getenv("CLOUD_RUN_DEEP_AGENT_JOB", "")
    GCS_BUCKET = os.getenv("GCS_BUCKET", "")

try:
    from app.error_logger import log_error
except ImportError:
    def log_error(context: str, error: BaseException, details: str | None = None) -> None:
        # error_logger.py自体が読めない場合でも、ERROR_LOG.mdへ簡易ログを残します。
        error_log_path = Path(__file__).resolve().parent / "ERROR_LOG.md"
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        error_log_path.open("a", encoding="utf-8").write(
            f"\n## Import-time logging fallback\n\n"
            f"- Context: {context}\n"
            f"- Error Type: {type(error).__name__}\n"
            f"- Message: {error}\n"
            f"- Details: {details or ''}\n"
        )


# Streamlitページ全体の設定です。最初のStreamlit命令として呼ぶ必要があります。
st.set_page_config(page_title="Recipe RAG Chatbot", layout="wide")


@st.cache_resource(show_spinner="Loading recipe knowledge base...")
def load_chatbot(force_rebuild_index: bool = False, llm_backend: str | None = None):
    # RAG chatbotの初期化はembedding/index読み込みが重いため、Streamlitのresource cacheに載せます。
    # load_chatbot.clear() を呼ぶと、次回アクセス時にindexを再読み込み・再構築できます。
    from app.rag_chatbot import RecipeRAGChatbot

    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index, llm_backend=llm_backend)

def apply_styles() -> None:
    # 画面全体の幅、色、入力、チャット、source表示をCSSで整えます。
    st.markdown(
        """
        <style>
        :root {
            --recipe-primary: #9A3412;
            --recipe-primary-strong: #7C2D12;
            --recipe-secondary: #C2410C;
            --recipe-accent: #059669;
            --recipe-bg: #FFFBEB;
            --recipe-surface: #FFF7ED;
            --recipe-card: #FFFFFF;
            --recipe-muted: #F8F2F0;
            --recipe-border: #F2D8C9;
            --recipe-text: #0F172A;
            --recipe-subtle: #6B4F3F;
            --recipe-ring: rgba(154, 52, 18, 0.28);
            --recipe-shadow: 0 18px 45px rgba(154, 52, 18, 0.10);
        }

        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 12% 0%, rgba(251, 146, 60, 0.18), transparent 30rem),
                linear-gradient(180deg, #FFFBEB 0%, #FFF7ED 42%, #FFFFFF 100%);
            color: var(--recipe-text);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.15rem;
            padding-bottom: 5.5rem;
        }

        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] { right: 1rem; }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, #431407 0%, #7C2D12 48%, #9A3412 100%);
            border-right: 1px solid rgba(255, 237, 213, 0.24);
        }

        [data-testid="stSidebar"] * {
            color: #FFF7ED;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] .stCaptionContainer,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] small {
            color: rgba(255, 247, 237, 0.76) !important;
        }

        [data-testid="stSidebar"] [data-testid="stExpander"] {
            background: rgba(255, 247, 237, 0.10);
            border: 1px solid rgba(255, 237, 213, 0.22);
            border-radius: 8px;
            overflow: hidden;
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            background: rgba(255, 251, 235, 0.96) !important;
            color: #1F2937 !important;
            border: 1px solid rgba(255, 237, 213, 0.64) !important;
        }

        [data-testid="stSidebar"] .stButton button {
            background: rgba(255, 251, 235, 0.96) !important;
            color: #7C2D12 !important;
            border-color: rgba(255, 237, 213, 0.72) !important;
        }

        [data-testid="stSidebar"] .stButton button p,
        [data-testid="stSidebar"] .stButton button span {
            color: #7C2D12 !important;
        }

        .recipe-brand {
            padding: 0.35rem 0 1rem;
        }

        .recipe-brand__kicker {
            color: #FDBA74;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        .recipe-brand__title {
            color: #FFF7ED;
            font-size: 1.55rem;
            line-height: 1.1;
            font-weight: 850;
            margin-top: 0.25rem;
        }

        .recipe-brand__copy {
            color: rgba(255, 247, 237, 0.78);
            font-size: 0.88rem;
            line-height: 1.55;
            margin-top: 0.55rem;
        }

        .recipe-hero {
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(135deg, rgba(154, 52, 18, 0.96), rgba(194, 65, 12, 0.88)),
                linear-gradient(90deg, #9A3412, #C2410C);
            border: 1px solid rgba(154, 52, 18, 0.14);
            border-radius: 8px;
            box-shadow: var(--recipe-shadow);
            padding: clamp(1.15rem, 2.6vw, 2rem);
            margin: 0.1rem 0 1.15rem;
        }

        .recipe-hero:after {
            content: "";
            position: absolute;
            inset: auto -8rem -10rem auto;
            width: 22rem;
            height: 22rem;
            background:
                linear-gradient(45deg, transparent 0 42%, rgba(255, 247, 237, 0.16) 42% 58%, transparent 58% 100%),
                linear-gradient(-45deg, transparent 0 42%, rgba(255, 237, 213, 0.18) 42% 58%, transparent 58% 100%);
            transform: rotate(12deg);
        }

        .recipe-hero__content {
            position: relative;
            z-index: 1;
            max-width: 760px;
        }

        .recipe-eyebrow {
            color: #FED7AA;
            font-size: 0.74rem;
            font-weight: 850;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }

        .recipe-hero h1 {
            color: #FFFFFF;
            font-size: clamp(2rem, 5vw, 4.2rem);
            line-height: 0.98;
            font-weight: 900;
            margin: 0;
        }

        .recipe-hero p {
            color: rgba(255, 247, 237, 0.86);
            font-size: clamp(1rem, 1.8vw, 1.18rem);
            line-height: 1.7;
            max-width: 720px;
            margin: 0.9rem 0 0;
        }

        .recipe-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1.2rem;
        }

        .recipe-badge {
            display: inline-flex;
            align-items: center;
            min-height: 2.35rem;
            padding: 0.5rem 0.78rem;
            border: 1px solid rgba(255, 237, 213, 0.35);
            border-radius: 8px;
            background: rgba(255, 251, 235, 0.14);
            color: #FFF7ED;
            font-size: 0.86rem;
            font-weight: 750;
            backdrop-filter: blur(8px);
        }

        .recipe-section-title {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 1.25rem 0 0.45rem;
        }

        .recipe-section-title__bar {
            width: 0.42rem;
            height: 1.8rem;
            border-radius: 999px;
            background: var(--recipe-secondary);
        }

        .recipe-section-title h2 {
            font-size: clamp(1.35rem, 2.4vw, 2rem);
            line-height: 1.15;
            margin: 0;
            color: var(--recipe-text);
        }

        .recipe-section-copy {
            color: var(--recipe-subtle);
            line-height: 1.65;
            margin: 0 0 1rem;
            max-width: 760px;
        }

        .recipe-status-row {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.9rem 0 1.15rem;
        }

        .recipe-status-card {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid var(--recipe-border);
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 10px 28px rgba(154, 52, 18, 0.07);
        }

        .recipe-status-card__label {
            color: var(--recipe-subtle);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        .recipe-status-card__value {
            color: var(--recipe-text);
            font-size: 0.96rem;
            font-weight: 800;
            margin-top: 0.28rem;
            overflow-wrap: anywhere;
        }

        .source-chip {
            display: inline-block;
            padding: 0.32rem 0.58rem;
            margin: 0.14rem;
            border: 1px solid var(--recipe-border);
            border-radius: 999px;
            font-size: 0.78rem;
            color: var(--recipe-primary-strong);
            background: #FFF7ED;
            max-width: 100%;
            overflow-wrap: anywhere;
        }

        .chat-limit-note {
            display: inline-flex;
            align-items: center;
            min-height: 2.35rem;
            padding: 0.52rem 0.78rem;
            border: 1px solid var(--recipe-border);
            border-radius: 8px;
            background: #FFF7ED;
            color: var(--recipe-primary-strong);
            font-size: 0.86rem;
            font-weight: 750;
            margin: 0.25rem 0 0.85rem;
        }

        .stButton button,
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px !important;
            min-height: 2.8rem;
            border: 1px solid var(--recipe-border) !important;
            font-weight: 800 !important;
            transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease;
            cursor: pointer;
        }

        .stButton button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(154, 52, 18, 0.14);
            border-color: rgba(154, 52, 18, 0.5) !important;
        }

        .stButton button[kind="primary"],
        button[kind="primary"] {
            background: linear-gradient(135deg, var(--recipe-primary), var(--recipe-secondary)) !important;
            border-color: var(--recipe-primary) !important;
            color: #FFFFFF !important;
        }

        button:focus,
        input:focus,
        textarea:focus,
        [role="radiogroup"] label:focus-within {
            outline: 3px solid var(--recipe-ring) !important;
            outline-offset: 2px !important;
            box-shadow: none !important;
        }

        input, textarea, [data-baseweb="select"] > div {
            border-radius: 8px !important;
            border-color: var(--recipe-border) !important;
        }

        textarea, input {
            background: rgba(255, 255, 255, 0.92) !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--recipe-border);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.78);
            box-shadow: 0 8px 22px rgba(154, 52, 18, 0.06);
            overflow: hidden;
        }

        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.84);
            border: 1px solid var(--recipe-border);
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 8px 22px rgba(154, 52, 18, 0.06);
        }

        [data-testid="stChatMessage"] {
            border-radius: 8px;
            border: 1px solid rgba(242, 216, 201, 0.78);
            background: rgba(255, 255, 255, 0.78);
            box-shadow: 0 8px 24px rgba(154, 52, 18, 0.06);
        }

        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
            background: #FFF7ED;
        }

        [data-testid="stChatInput"] {
            background: rgba(255, 251, 235, 0.82);
            border-top: 1px solid rgba(242, 216, 201, 0.82);
            backdrop-filter: blur(12px);
        }

        [data-testid="stChatInput"] textarea {
            min-height: 3rem !important;
        }

        hr {
            border-color: var(--recipe-border) !important;
            opacity: 1;
        }

        .stDataFrame, [data-testid="stTable"] {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--recipe-border);
        }

        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
                transition-duration: 0.01ms !important;
            }
        }

        @media (max-width: 720px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
                padding-top: 0.8rem;
            }
            .recipe-hero {
                padding: 1.05rem;
                margin-top: 0;
            }
            .recipe-badge {
                width: 100%;
                justify-content: center;
            }
            .recipe-status-row {
                grid-template-columns: 1fr;
            }
            div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
            .stButton button { width: 100%; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.markdown(
        """
        <div class="recipe-brand">
            <div class="recipe-brand__kicker">Recipe Intelligence</div>
            <div class="recipe-brand__title">Recipe RAG</div>
            <div class="recipe-brand__copy">保存済みレシピ参照を検索し、和食の調理判断を一緒に組み立てます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_app_header(mode: str) -> None:
    mode_copy = {
        "OpenRouter RAG Chat": "保存済みレシピ参照と画像を組み合わせ、根拠のある調理提案を返します。",
        "OpenRouter Chat": "RAGを使わず、軽い相談や下ごしらえの確認に使えます。",
        "past conversation": "過去の相談を日付とAI種別で振り返れます。",
        "Crawl4AI Check": "Web抽出の挙動と取得品質を確認できます。",
        "Adaptive Crawl": "サイト内を段階的に探索し、調査結果を整理します。",
    }
    st.markdown(
        f"""
        <section class="recipe-hero">
            <div class="recipe-hero__content">
                <div class="recipe-eyebrow">Orange Edition</div>
                <h1>Recipe Inference RAG</h1>
                <p>{escape(mode_copy.get(mode, "レシピ調査と会話を一つの作業面で扱えます。"))}</p>
                <div class="recipe-badges">
                    <span class="recipe-badge">OpenRouter free model</span>
                    <span class="recipe-badge">Local recipe retrieval</span>
                    <span class="recipe-badge">Cloud cost guarded</span>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="recipe-section-title">
            <span class="recipe-section-title__bar"></span>
            <h2>{escape(title)}</h2>
        </div>
        <p class="recipe-section-copy">{escape(copy)}</p>
        """,
        unsafe_allow_html=True,
    )


def render_status_cards(items: list[tuple[str, str]]) -> None:
    cards = "\n".join(
        (
            '<div class="recipe-status-card">'
            f'<div class="recipe-status-card__label">{escape(label)}</div>'
            f'<div class="recipe-status-card__value">{escape(value)}</div>'
            "</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="recipe-status-row">{cards}</div>', unsafe_allow_html=True)


def show_recipe_source_error(exc: Exception) -> None:
    # RAG用データの読み込みに失敗した時の専用エラー表示です。
    log_error("Recipe source loading", exc)
    if is_openrouter_config_error(exc):
        show_openrouter_config_error(exc)
        return

    st.error("RAG用のレシピ文書を読み込めませんでした。")
    st.info(
        "Just One CookbookがPythonからの自動取得に403を返している可能性があります。"
        f"ブラウザで保存したレシピページの `.html`, `.txt`, `.md` を `{LOCAL_RECIPE_DIR}` に入れて、"
        "`python scripts/rebuild_index.py` を実行してください。"
    )
    with st.expander("詳細エラー"):
        st.code(str(exc))


def is_openrouter_config_error(exc: Exception) -> bool:
    # OpenRouter APIキー・モデル安全性由来のエラーかどうかを文字列でざっくり判定します。
    message = str(exc)
    return (
        "OPENROUTER_API_KEY" in message
        or "Unsafe OpenRouter model" in message
        or "Use only models ending with ':free'" in message
    )


def show_openrouter_config_error(exc: Exception) -> None:
    # OpenRouter APIキー不足・有料モデル指定の時に、ユーザーが次に取る行動を表示します。
    message = str(exc)
    if "Unsafe OpenRouter model" in message:
        st.error("OpenRouterのモデル指定が無料モデルではありません。")
        st.info("`.env` の `OPENROUTER_MODEL` は必ず `:free` で終わる model id にしてください。")
    else:
        st.error("OpenRouter API keyが設定されていない、または利用できません。")
        st.info(
            "`.env` に `OPENROUTER_API_KEY=...` を設定してください。"
            "`OPENROUTER_MODEL` は `google/gemma-4-26b-a4b-it:free` のように `:free` で終わるモデルだけ使えます。"
        )
    with st.expander("詳細エラー"):
        st.code(message)


def show_generation_error(exc: Exception, fallback_message: str) -> None:
    # Chat/JSON/OpenRouter回答生成で共通利用するエラー表示です。
    if is_openrouter_config_error(exc):
        show_openrouter_config_error(exc)
        return

    st.error(fallback_message)
    with st.expander("エラー詳細"):
        st.code(str(exc))


def render_llm_trace(title: str, steps: list[str]) -> None:
    if not steps:
        return
    with st.expander(title, expanded=False):
        for step in steps:
            st.write(step)


def format_rate_limit_details(exc: Exception, stage: str) -> str:
    model = getattr(exc, "model", active_openrouter_model_label())
    status_code = getattr(exc, "status_code", "unknown")
    message = getattr(exc, "message", str(exc))
    return f"stage={stage}, model={model}, status_code={status_code}, message={message}"


def has_local_recipe_files() -> bool:
    # data/joc_pages と data/web_recipe_reference に保存済みのレシピ文書があるか確認します。
    for directory in (LOCAL_RECIPE_DIR, WEB_RECIPE_REFERENCE_DIR):
        if not directory.exists():
            continue
        if any(
            path.is_file() and path.suffix.lower() in {".html", ".htm", ".txt", ".md"}
            for path in directory.iterdir()
        ):
            return True
    return False


def has_gcs_recipe_files() -> bool:
    try:
        from app.gcs_storage import is_available, list_text_objects

        return is_available() and bool(list_text_objects("joc_pages") or list_text_objects("web_recipe_reference"))
    except Exception:
        return False


def gcs_storage_available() -> bool:
    try:
        from app.gcs_storage import is_available

        return is_available()
    except Exception:
        return False


def has_vector_index() -> bool:
    # TurboVec indexがすでに作成済みか確認します。
    return VECTOR_INDEX_DIR.exists() and any(VECTOR_INDEX_DIR.iterdir())


def recipe_knowledge_ready(force_rebuild: bool) -> bool:
    # RAG実行前の準備確認です。
    # 再構築する場合は元データが必要で、再構築しない場合は既存indexだけでも動けます。
    if force_rebuild:
        return has_local_recipe_files() or has_gcs_recipe_files()
    return has_vector_index() or has_local_recipe_files() or has_gcs_recipe_files()


def show_missing_recipe_data_message() -> None:
    # RAGに必要なローカル文書/indexがない時の案内です。
    st.warning("RAGに使えるレシピデータがまだありません。")
    st.info(
        "左サイドバーの「ページをdataに保存」または「Deep Agent自動収集」からレシピ参照を保存してください。"
        f"保存先は `{LOCAL_RECIPE_DIR}` または `{WEB_RECIPE_REFERENCE_DIR}` です。"
    )


def render_sidebar() -> tuple[bool, str]:
    # サイドバーでは、画面モード選択・RAG index再構築・レシピページ保存を扱います。
    from app.deep_agent import run_deep_agent_recipe_collection_with_details
    from app.scraper import save_recipe_page_from_url

    with st.sidebar:
        render_sidebar_brand()
        # このボタンを押した場合、次回RAG実行時に既存indexではなく文書から作り直します。
        force_rebuild = st.button("RAGインデックスを再作成", use_container_width=True)
        # このradioがメイン画面の「ページ切り替え」として働きます。
        mode_labels = {
            "OpenRouter RAG Chat": "RAGチャット",
            "OpenRouter Chat": "クイック相談",
            "past conversation": "会話履歴",
            "Crawl4AI Check": "抽出チェック",
            "Adaptive Crawl": "サイト調査",
        }
        mode = st.radio(
            "モード",
            [
                "OpenRouter RAG Chat",
                "OpenRouter Chat",
                "past conversation",
                "Crawl4AI Check",
                "Adaptive Crawl",
            ],
            label_visibility="collapsed",
            format_func=lambda value: mode_labels.get(value, value),
        )
        st.divider()

        with st.expander("ページをdataに保存", expanded=True):
            # URLを直接指定してレシピページを保存する、最も確実な収集方法です。
            recipe_url = st.text_input("Recipe URL", placeholder="https://www.justonecookbook.com/tonjiru/")
            if st.button("URLを保存", use_container_width=True):
                if not recipe_url:
                    st.warning("保存したいURLを入力してください。")
                else:
                    try:
                        saved = save_recipe_page_from_url(recipe_url)
                        # 新しい文書を保存したので、古いRAG chatbot cacheを破棄します。
                        load_chatbot.clear()
                        # 次回Chat/JSON時にindex再構築を自動実行するためのフラグです。
                        st.session_state.rebuild_index_next = True
                        st.success(f"保存しました: {saved.path.name} ({saved.text_chars} chars)")
                        st.caption("次回のChat/JSON実行時にRAGインデックスを自動で再作成します。")
                    except Exception as exc:
                        log_error("Sidebar URL save", exc, details=f"recipe_url={recipe_url}")
                        st.error("ページを保存できませんでした。403の場合はサイト側が自動取得を拒否しています。")
                        st.code(str(exc))

        with st.expander("Deep Agent自動収集"):
            # crawl4ai Agentic CrawlerはLLMで検索計画を立て、Best-first crawlでWeb参照を保存します。
            st.warning("crawl4ai Agentic CrawlerはLLM、Web検索、複数ページのクロールを使うため、数分かかることがあります。")
            deep_agent_unavailable = False
            st.caption(
                f"LLM: `{DEEP_AGENT_LLM_BACKEND}` / default model: `{OPENROUTER_MODEL}`。"
                f"Web検索、seed URL選択、crawl4ai deep crawl、保存を実行します。保存先: `{WEB_RECIPE_REFERENCE_DIR}`"
            )
            gcs_available = gcs_storage_available()
            if GCS_BUCKET and gcs_available:
                st.caption(f"Cloud Storage: `gs://{GCS_BUCKET}`")
            elif GCS_BUCKET:
                st.caption("Cloud Storage設定はありますが、この環境ではGCSクライアントを利用できないためローカル保存に切り替えます。")
            if CLOUD_RUN_DEEP_AGENT_JOB:
                st.caption(f"Cloud Run Job: `{CLOUD_RUN_DEEP_AGENT_JOB}`")
            sidebar_job = st.session_state.get("sidebar_deep_agent_job")
            if sidebar_job and GCS_BUCKET and gcs_available:
                from app.gcs_storage import download_json, gcs_uri

                status_object = f"results/{sidebar_job['request_id']}/status.json"
                st.caption(f"Latest job status: `{gcs_uri(status_object)}`")
                if st.button("Deep Agent Job状態を更新", use_container_width=True):
                    try:
                        status = download_json(status_object)
                    except FileNotFoundError:
                        st.info("Job statusはまだ作成されていません。少し待ってください。")
                    except Exception as exc:
                        log_error("Sidebar Deep Agent Job status", exc, details=f"request_id={sidebar_job['request_id']}")
                        st.error("Job statusを読み込めませんでした。")
                        st.code(str(exc))
                    else:
                        st.json(status)
                        if status.get("status") == "succeeded":
                            load_chatbot.clear()
                            st.session_state.rebuild_index_next = True
                            st.success("Deep Agent Jobが完了しました。次回Chat/JSON実行時にRAGインデックスを再作成します。")
                        elif status.get("status") == "failed":
                            log_error(
                                "Sidebar Deep Agent Job failed",
                                RuntimeError(str(status.get("error") or "Deep Agent Job failed.")),
                                details=f"request_id={sidebar_job['request_id']}\nstatus={status}",
                            )
                            st.error("Deep Agent Jobが失敗しました。")
            deep_query = st.text_input("収集したいレシピ/調査テーマ", placeholder="omurice recipe technique and variations")
            deep_max_pages = st.slider("最大保存ページ数", min_value=1, max_value=5, value=3)
            if st.button("Deep Agentで収集", use_container_width=True, disabled=deep_agent_unavailable):
                if not deep_query:
                    st.warning("収集したいレシピ名やテーマを入力してください。")
                else:
                    with st.spinner("Agentic CrawlerがWeb上の関連ページを調査して保存しています。時間がかかります..."):
                        try:
                            if GCS_BUCKET and CLOUD_RUN_DEEP_AGENT_JOB and gcs_available:
                                from app.cloud_run_jobs import run_deep_agent_job
                                from app.gcs_storage import gcs_uri, upload_json

                                request_id = str(uuid.uuid4())
                                request_object = f"requests/{request_id}.json"
                                upload_json(
                                    request_object,
                                    {
                                        "request_id": request_id,
                                        "query": deep_query,
                                        "max_pages": deep_max_pages,
                                        "created_at": datetime.utcnow().isoformat(),
                                    },
                                )
                                operation = run_deep_agent_job(
                                    request_object=request_object,
                                    query=deep_query,
                                    max_pages=deep_max_pages,
                                )
                                st.success("Cloud Run Jobを開始しました。")
                                st.caption(f"request_id: `{request_id}`")
                                st.caption(f"status: `{gcs_uri(f'results/{request_id}/status.json')}`")
                                st.session_state.sidebar_deep_agent_job = {
                                    "request_id": request_id,
                                    "query": deep_query,
                                }
                                with st.expander("Cloud Run operation"):
                                    st.json(operation)
                                return force_rebuild, mode

                            result = run_deep_agent_recipe_collection_with_details(
                                deep_query,
                                max_pages=deep_max_pages,
                            )
                            # Deep Agentが保存したページもRAGの新規材料なので、cacheを消して再構築予約します。
                            load_chatbot.clear()
                            st.session_state.rebuild_index_next = True
                            st.success(f"{len(result.saved_pages)}件保存しました。")
                            st.caption(result.notes)
                            with st.expander("Deep Agentの実行内容"):
                                # デバッグしやすいよう、Agentが考えた検索語と選んだseed URLをUIに出します。
                                st.write("Search queries")
                                st.json(result.search_queries)
                                st.write("Candidate URLs")
                                st.json(result.candidate_urls)
                                st.write("Selected URLs")
                                st.json(result.selected_urls)
                                if result.crawl_errors:
                                    st.write("Crawl errors")
                                    st.json(result.crawl_errors[:10])
                            for saved_page in result.saved_pages:
                                st.caption(f"{saved_page.path.name} - {saved_page.url}")
                        except Exception as exc:
                            log_error(
                                "Sidebar crawl4ai Agentic Crawler collection",
                                exc,
                                details=f"query={deep_query}, max_pages={deep_max_pages}",
                            )
                            st.error("Agentic Crawler収集に失敗しました。設定やネットワーク状態を確認してください。")
                            st.code(str(exc))

    return force_rebuild, mode


def ensure_chat_history() -> None:
    # RAG Chat用の会話履歴をStreamlit session_stateに初期化します。
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "こんにちは。保存済みレシピ参照を元に、和食レシピを一緒に組み立てます。",
            }
        ]
    st.session_state.setdefault("openrouter_rag_turn_count", count_user_turns(st.session_state.messages))


def ensure_openrouter_chat_history() -> None:
    # OpenRouter単体テスト用の履歴です。RAGチャットの履歴とは分けます。
    if "openrouter_messages" not in st.session_state:
        st.session_state.openrouter_messages = [
            {
                "role": "assistant",
                "content": "こんにちは。RAGを使わず、OpenRouter free modelだけで回答します。",
            }
        ]
    st.session_state.setdefault("openrouter_turn_count", count_user_turns(st.session_state.openrouter_messages))


MAX_CHAT_TURNS = 5
IMAGE_SYSTEM_PROMPT = """When the user provides images, inspect them as part of the request.
Use the text prompt as the main task, and use the image only for observable visual evidence.
If the image could influence recipe selection, ingredient identification, substitutions, cooking stage, plating, or tool choice, mention that explicitly.
For RAG or Deep Agent workflows, use image observations to form better search/retrieval queries, but do not invent invisible details.
Do not reveal hidden reasoning or chain-of-thought; provide a concise natural-language explanation of useful observations and actions."""


def count_user_turns(messages: list[dict[str, Any]]) -> int:
    return sum(1 for message in messages if message.get("role") == "user")


def chat_turns_remaining(messages_key: str) -> int:
    return max(0, MAX_CHAT_TURNS - count_user_turns(st.session_state.get(messages_key, [])))


def render_turn_limit(messages_key: str) -> bool:
    remaining = chat_turns_remaining(messages_key)
    st.markdown(
        f'<div class="chat-limit-note">このchatは最大{MAX_CHAT_TURNS}回まで質問できます。残り {remaining} 回。</div>',
        unsafe_allow_html=True,
    )
    if remaining <= 0:
        st.warning("このchatの上限に達しました。新しく始める場合はページを再読み込みするか、会話履歴をリセットしてください。")
        return False
    return True


def image_to_data_url(uploaded_file) -> str:
    content_type = uploaded_file.type or "image/png"
    encoded = base64.b64encode(uploaded_file.getvalue()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def prepare_image_payloads(image_files: list[Any]) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    for image_file in image_files:
        payloads.append(
            {
                "name": getattr(image_file, "name", "camera-image"),
                "type": getattr(image_file, "type", "image/png") or "image/png",
                "data_url": image_to_data_url(image_file),
            }
        )
    return payloads


def build_image_prompt_text(question: str, image_payloads: list[dict[str, str]]) -> str:
    if not image_payloads:
        return question
    names = ", ".join(image.get("name", "camera-image") for image in image_payloads)
    return (
        f"{IMAGE_SYSTEM_PROMPT}\n\n"
        f"User text prompt:\n{question}\n\n"
        f"Attached image files: {names}"
    )


def build_multimodal_content(question: str, image_payloads: list[dict[str, str]]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": build_image_prompt_text(question, image_payloads)}]
    for image_payload in image_payloads:
        content.append({"type": "image_url", "image_url": {"url": image_payload["data_url"]}})
    return content


def render_image_input(key_prefix: str) -> list[Any]:
    with st.expander("画像入力", expanded=False):
        mode = st.radio(
            "画像の追加方法",
            ["アップロード", "スマホ/カメラ"],
            horizontal=True,
            key=f"{key_prefix}_image_mode",
        )
        image_files: list[Any] = []
        if mode == "スマホ/カメラ":
            captured = st.camera_input("カメラで撮影", key=f"{key_prefix}_camera")
            if captured is not None:
                image_files.append(captured)
        uploaded = st.file_uploader(
            "画像をアップロード",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key=f"{key_prefix}_upload",
        )
        if uploaded:
            image_files.extend(uploaded)
        if image_files:
            st.caption("一時プレビュー")
            preview_cols = st.columns(min(3, len(image_files)))
            for index, image_file in enumerate(image_files):
                preview_cols[index % len(preview_cols)].image(
                    image_file,
                    caption=getattr(image_file, "name", f"image-{index + 1}"),
                    use_container_width=True,
                )
        return image_files


def stream_markdown_text(text: str) -> str:
    def chunks():
        for index in range(0, len(text), 24):
            yield text[index : index + 24]
            time.sleep(0.012)

    return st.write_stream(chunks())


def parse_yes_no(value: str) -> bool | None:
    normalized = value.strip().lower().strip(" .。!！?？")
    yes_values = {"yes", "y", "はい", "うん", "お願いします", "探して", "実行", "実行して"}
    no_values = {"no", "n", "いいえ", "不要", "しない", "なし", "大丈夫"}
    if normalized in yes_values:
        return True
    if normalized in no_values:
        return False
    return None


def render_sources(sources: list[str]) -> None:
    if not sources:
        return
    st.caption("Sources")
    st.markdown(
        " ".join(f'<span class="source-chip">{escape(url)}</span>' for url in sources),
        unsafe_allow_html=True,
    )


def active_openrouter_model_label() -> str:
    try:
        from app.openrouter import get_active_openrouter_model

        return get_active_openrouter_model()
    except Exception:
        return OPENROUTER_MODEL


def render_openrouter_model_switch(task: dict) -> None:
    from app.openrouter import ranked_free_openrouter_models, set_active_openrouter_model

    st.warning("OpenRouter free modelの利用制限に達しました。別の無料モデルへ切り替えて、このタスクを続行できます。")
    if task.get("rate_limited_model"):
        st.caption(f"Rate limited model: `{task['rate_limited_model']}`")
    if task.get("rate_limit_status_code"):
        st.caption(f"OpenRouter status: `{task['rate_limit_status_code']}`")
    if task.get("rate_limit_message"):
        with st.expander("OpenRouter rate limit message"):
            st.code(str(task["rate_limit_message"]))

    try:
        candidates = ranked_free_openrouter_models(limit=5)
    except Exception as exc:
        log_error("OpenRouter free model listing", exc)
        st.error("OpenRouterの無料モデル一覧を取得できませんでした。")
        with st.expander("詳細エラー"):
            st.code(str(exc))
        st.stop()

    options = [model.id for model in candidates]
    if not options:
        st.error("切り替え可能なOpenRouter free modelが見つかりませんでした。")
        st.stop()

    ranking_rows = [model for model in candidates if model.weekly_tokens is not None]
    if ranking_rows:
        st.caption("OpenRouter全体で世界中のユーザーが直近7日間に処理したtoken数のfree model上位5件")
        st.dataframe(
            [
                {
                    "model_id": model.id,
                    "model_name": model.name,
                    "last_7_days_total_tokens": int(model.weekly_tokens or 0),
                }
                for model in ranking_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("OpenRouterの7日間tokenランキングを取得できなかったため、取得できたfree model候補を表示します。")

    selected = st.selectbox(
        "切り替え先 free model",
        options,
        format_func=lambda model_id: next(
            (
                f"{model.id} - {model.name}"
                + (f" / 7d tokens {model.weekly_tokens:,}" if model.weekly_tokens is not None else "")
                + (f" / context {model.context_length}" if model.context_length else "")
                for model in candidates
                if model.id == model_id
            ),
            model_id,
        ),
    )
    if st.button("このモデルに切り替えて続行", type="primary"):
        set_active_openrouter_model(selected)
        task["needs_model_switch"] = False
        task["selected_model"] = selected
        st.session_state.openrouter_pending_task = task
        load_chatbot.clear()
        st.rerun()
    st.stop()


def defer_for_openrouter_model_switch(exc: Exception, task: dict) -> bool:
    from app.openrouter import OpenRouterRateLimitError

    if not isinstance(exc, OpenRouterRateLimitError):
        return False
    task["needs_model_switch"] = True
    task["rate_limited_model"] = exc.model
    task["rate_limit_status_code"] = exc.status_code
    task["rate_limit_message"] = str(exc)
    task["rate_limit_payload"] = getattr(exc, "payload", {})
    st.session_state.openrouter_pending_task = task
    render_openrouter_model_switch(task)
    return True


def deep_agent_offer_message(question: str) -> str:
    return (
        "ローカルのベクトルDBには、この質問へ直接答えるのに十分な情報が見つかりませんでした。\n\n"
        "Deep Agentで対象レシピの情報をWebから探して保存し、RAGインデックスを更新してから回答しますか？\n\n"
        f"対象: {question}\n\n"
        "許可する場合は「Deep Agentを実行」、許可しない場合は「実行しない」を押してください。"
    )


def deep_agent_denied_message(question: str) -> str:
    return (
        "Deep Agentの実行が許可されなかったため、この会話はここで終了します。\n\n"
        "現在のRAGデータでは、この質問に十分な根拠を持って回答できません。\n"
        "正確なレシピ提案を行うには、Deep Agentによる自動データ収集をおすすめします。\n\n"
        f"対象: {question}"
    )


def render_deep_agent_permission_buttons(
    question: str,
    *,
    key_prefix: str,
    image_payloads: list[dict[str, str]] | None = None,
) -> None:
    col_allow, col_deny = st.columns(2)
    if col_allow.button("Deep Agentを実行", type="primary", key=f"{key_prefix}_allow"):
        st.session_state.openrouter_pending_task = {
            "type": "openrouter_rag_deep_agent_choice",
            "question": question,
            "choice": True,
            "image_payloads": image_payloads or [],
        }
        st.session_state.openrouter_rag_deep_agent_pending = None
        st.rerun()
    if col_deny.button("実行しない", key=f"{key_prefix}_deny"):
        st.session_state.openrouter_pending_task = {
            "type": "openrouter_rag_deep_agent_choice",
            "question": question,
            "choice": False,
            "image_payloads": image_payloads or [],
        }
        st.session_state.openrouter_rag_deep_agent_pending = None
        st.rerun()


def start_cloud_deep_agent_collection(question: str, max_pages: int = 3) -> str:
    from app.cloud_run_jobs import run_deep_agent_job
    from app.gcs_storage import upload_json

    request_id = str(uuid.uuid4())
    request_object = f"requests/{request_id}.json"
    upload_json(
        request_object,
        {
            "request_id": request_id,
            "query": question,
            "max_pages": max_pages,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    run_deep_agent_job(request_object=request_object, query=question, max_pages=max_pages)
    return request_id


def maybe_start_cloud_deep_agent(question: str, max_pages: int = 3) -> str | None:
    if not (GCS_BUCKET and CLOUD_RUN_DEEP_AGENT_JOB):
        return None
    if not gcs_storage_available():
        return None
    return start_cloud_deep_agent_collection(question, max_pages=max_pages)


def render_pending_deep_agent_job() -> bool:
    pending_job = st.session_state.get("openrouter_rag_deep_agent_job")
    if not pending_job:
        return False

    from app.gcs_storage import download_json, gcs_uri

    question = pending_job["question"]
    request_id = pending_job["request_id"]
    status_object = f"results/{request_id}/status.json"
    st.info("Deep AgentのCloud Run Jobを実行中です。完了後にRAGインデックスを再作成して回答します。")
    st.caption(f"Status: `{gcs_uri(status_object)}`")

    if not st.button("状態を更新して回答を続ける", type="primary", key=f"refresh_deep_agent_job_{request_id}"):
        return True

    try:
        status = download_json(status_object)
    except FileNotFoundError:
        st.warning("Job statusはまだ作成されていません。少し待ってから再度更新してください。")
        return True
    except Exception as exc:
        log_error("Deep Agent Cloud Run Job status read", exc, details=f"request_id={request_id}")
        st.error("Deep Agent Jobの状態を読み込めませんでした。")
        st.code(str(exc))
        return True

    job_status = str(status.get("status", "unknown"))
    if job_status == "running":
        st.info("Deep Agentはまだ実行中です。少し待ってから再度更新してください。")
        return True
    if job_status == "failed":
        exc = RuntimeError(str(status.get("error") or "Deep Agent Job failed."))
        log_error("Deep Agent Cloud Run Job failed", exc, details=f"request_id={request_id}\nstatus={status}")
        st.session_state.openrouter_rag_deep_agent_job = None
        message = "Deep Agent Jobが失敗しました。設定を確認してから、もう一度データ収集を実行してください。"
        st.error(message)
        st.code(str(status.get("error") or status))
        st.session_state.messages.append({"role": "assistant", "content": message})
        persist_current_conversation(
            ai_type="OpenRouter_RAG",
            messages_key="messages",
            conversation_key="openrouter_rag_conversation_id",
        )
        return True
    if job_status != "succeeded":
        st.warning(f"未知のJob状態です: {job_status}")
        st.json(status)
        return True

    try:
        with st.spinner("収集済みデータからRAGインデックスを再作成し、回答を生成しています..."):
            load_chatbot.clear()
            chatbot = ensure_rag_chatbot_capabilities(
                load_chatbot(True, "openrouter"),
                lambda: load_chatbot(True, "openrouter"),
            )
            response = chatbot.answer(question)
    except Exception as exc:
        log_error("Deep Agent Cloud Run Job post-processing", exc, details=f"request_id={request_id}, question={question}")
        st.error("Deep Agent収集後のRAG回答生成に失敗しました。")
        st.code(str(exc))
        return True

    prefix = f"Deep Agentで{len(status.get('saved_pages') or [])}件の参照を保存しました。\n\n"
    with st.chat_message("assistant"):
        st.markdown(prefix + response.answer)
        render_sources(response.sources)
    st.session_state.messages.append({"role": "assistant", "content": prefix + response.answer})
    st.session_state.rebuild_index_next = False
    st.session_state.openrouter_rag_deep_agent_job = None
    persist_current_conversation(
        ai_type="OpenRouter_RAG",
        messages_key="messages",
        conversation_key="openrouter_rag_conversation_id",
    )
    st.rerun()
    return True


def run_chat_deep_agent_answer(
    *,
    question: str,
    force_rebuild: bool,
    load_current_chatbot,
):
    from app.deep_agent import run_deep_agent_recipe_collection_with_details

    cloud_request_id = maybe_start_cloud_deep_agent(question, max_pages=3)
    if cloud_request_id:
        st.session_state.openrouter_rag_deep_agent_job = {
            "question": question,
            "request_id": cloud_request_id,
        }
        return None, None

    result = run_deep_agent_recipe_collection_with_details(question, max_pages=3)
    load_chatbot.clear()
    chatbot = load_current_chatbot(force_rebuild)
    response = chatbot.answer(question)
    return result, response


def render_deep_agent_failure(exc: Exception, *, question: str, result=None) -> None:
    st.error("Deep Agent自動収集に失敗しました。")
    st.caption("ベクトルDBに十分な情報がなかったため自動収集を試しましたが、収集または回答生成で停止しました。")
    if result is not None:
        with st.expander("Deep Agent収集内容"):
            st.write("Search queries")
            st.json(getattr(result, "search_queries", []))
            st.write("Candidate URLs")
            st.json(getattr(result, "candidate_urls", []))
            st.write("Selected URLs")
            st.json(getattr(result, "selected_urls", []))
            crawl_errors = getattr(result, "crawl_errors", [])
            if crawl_errors:
                st.write("Crawl errors")
                st.json(crawl_errors[:10])
    with st.expander("エラー詳細"):
        st.code(f"question={question}\n{type(exc).__name__}: {exc}")


def ensure_rag_chatbot_capabilities(chatbot, reload_chatbot):
    required_methods = ("retrieve", "has_sufficient_context", "answer_from_docs", "answer_from_model_knowledge")
    if all(hasattr(chatbot, method_name) for method_name in required_methods):
        return chatbot
    load_chatbot.clear()
    return reload_chatbot()


def persist_current_conversation(*, ai_type: str, messages_key: str, conversation_key: str) -> None:
    from app.database import save_chat_conversation, save_chat_conversation_fallback

    current_id = st.session_state.get(conversation_key)
    if st.session_state.get("postgres_unavailable"):
        fallback_id = save_chat_conversation_fallback(
            ai_type=ai_type,
            messages=st.session_state.get(messages_key, []),
            conversation_id=str(current_id) if str(current_id).startswith("local-") else None,
        )
        st.session_state[conversation_key] = fallback_id
        return

    try:
        conversation_id = save_chat_conversation(
            ai_type=ai_type,
            messages=st.session_state.get(messages_key, []),
            conversation_id=current_id,
        )
        st.session_state[conversation_key] = conversation_id
    except Exception as exc:
        log_error("Chat conversation PostgreSQL save", exc, details=f"ai_type={ai_type}")
        st.session_state.postgres_unavailable = True
        st.session_state.conversation_save_error = str(exc)
        fallback_id = save_chat_conversation_fallback(
            ai_type=ai_type,
            messages=st.session_state.get(messages_key, []),
            conversation_id=str(current_id) if str(current_id).startswith("local-") else None,
        )
        st.session_state[conversation_key] = fallback_id


def show_postgres_recovery_hint() -> None:
    st.info("PostgreSQLが停止している可能性があります。過去会話をDBに保存・表示したい場合は、別ターミナルで次を実行してください。")
    st.code("docker compose -f docker/docker-compose.yml up -d db", language="bash")
    st.caption("DBを使わず続ける場合は、会話はローカル退避履歴に保存されます。")


def format_display_datetime(value) -> str:
    if not value:
        return "-"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value)
    # Database rows are stored as UTC-naive datetimes. Display them in JST.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M JST")


def render_past_conversation() -> None:
    from app.database import (
        fetch_chat_conversation,
        fetch_chat_conversation_fallback,
        fetch_chat_conversations,
        fetch_chat_conversations_fallback,
    )

    render_section_intro("会話履歴", "保存された相談を時系列で確認し、調理メモや過去の判断をすぐに再利用できます。")
    selected_id = st.session_state.get("selected_conversation_id")

    if selected_id:
        conversation = None
        try:
            if str(selected_id).startswith("local-"):
                conversation = fetch_chat_conversation_fallback(str(selected_id))
            else:
                conversation = fetch_chat_conversation(int(selected_id))
        except Exception as exc:
            log_error("Past conversation detail", exc, details=f"conversation_id={selected_id}")
            conversation = fetch_chat_conversation_fallback(str(selected_id))
        if not conversation:
            st.warning("選択した会話が見つかりませんでした。")
            if st.button("一覧に戻る"):
                st.session_state.selected_conversation_id = None
                st.rerun()
            return

        if st.button("一覧に戻る"):
            st.session_state.selected_conversation_id = None
            st.rerun()

        created_at = format_display_datetime(conversation.get("created_at"))
        col_date, col_label, col_ai = st.columns(3)
        col_date.metric("Date", created_at)
        col_label.metric("Conversation", f"conversation{conversation['id']}")
        col_ai.metric("AI", conversation["ai_type"])
        if conversation.get("storage") == "local_fallback":
            st.caption("PostgreSQLに接続できなかったため、ローカル退避履歴から表示しています。")
        st.divider()

        for message in conversation.get("messages") or []:
            role = message.get("role", "assistant")
            content = message.get("content", "")
            if not content:
                continue
            with st.chat_message(role):
                st.markdown(content)
        return

    try:
        conversations = fetch_chat_conversations()
    except Exception as exc:
        log_error("Past conversation list", exc)
        conversations = fetch_chat_conversations_fallback()
        if conversations:
            st.warning("PostgreSQLに接続できないため、ローカル退避履歴を表示しています。")
            show_postgres_recovery_hint()
            with st.expander("DB接続エラー"):
                st.code(str(exc))
        else:
            st.error("過去会話をDBから読み込めませんでした。")
            show_postgres_recovery_hint()
            st.info("まだローカル退避履歴もありません。チャットを実行すると、DB停止中でも退避履歴が作成されます。")
            with st.expander("エラー詳細"):
                st.code(str(exc))
            return
    else:
        fallback_conversations = fetch_chat_conversations_fallback()
        if fallback_conversations:
            conversations = conversations + [
                item
                for item in fallback_conversations
                if str(item.get("id")) not in {str(conversation.get("id")) for conversation in conversations}
            ]
            conversations = sorted(
                conversations,
                key=lambda item: item.get("created_at") or item.get("updated_at") or datetime.min,
                reverse=True,
            )

    if not conversations:
        st.info("保存済みの会話はまだありません。")
        return

    for conversation in conversations:
        created_at = format_display_datetime(conversation.get("created_at"))
        with st.container():
            col_date, col_label, col_ai = st.columns(3)
            col_date.markdown(f"**Date**  \n{created_at}")
            col_label.markdown(f"**Conversation**  \nconversation{conversation['id']}")
            col_ai.markdown(f"**AI**  \n{conversation['ai_type']}")
            if conversation.get("storage") == "local_fallback":
                st.caption("local fallback")
            if st.button("この会話を見る", key=f"view_conversation_{conversation['id']}", use_container_width=True):
                st.session_state.selected_conversation_id = conversation["id"]
                st.rerun()
            st.divider()


def load_openrouter_rag_chatbot_for_question(should_rebuild: bool):
    chatbot = load_chatbot(should_rebuild, "openrouter")
    chatbot = ensure_rag_chatbot_capabilities(
        chatbot,
        lambda: load_chatbot(should_rebuild, "openrouter"),
    )
    st.session_state.rebuild_index_next = False
    return chatbot


def retrieve_and_assess_openrouter_context(
    *,
    chatbot,
    question: str,
    image_payloads: list[dict[str, str]],
    llm_steps: list[str],
) -> tuple[str, list[Any], bool]:
    retrieval_question = build_image_prompt_text(question, image_payloads)
    llm_steps.append("RAG検索: ベクトルDBから関連チャンク取得")
    docs = chatbot.retrieve(retrieval_question)
    llm_steps.append("RAG context判定: OpenRouter free modelで十分性を判定")
    has_context = chatbot.has_sufficient_context(retrieval_question, docs)
    return retrieval_question, docs, has_context


def create_openrouter_rag_response(
    *,
    chatbot,
    question: str,
    docs: list[Any],
    image_payloads: list[dict[str, str]],
    llm_steps: list[str],
):
    llm_steps.append("mem0検索: 好み/制約の長期記憶を検索")
    llm_steps.append("RAG回答生成: OpenRouter free modelで回答作成")
    if image_payloads and hasattr(chatbot, "answer_from_docs_multimodal"):
        response = chatbot.answer_from_docs_multimodal(
            question,
            docs,
            build_multimodal_content(question, image_payloads),
        )
    else:
        response = chatbot.answer_from_docs(question, docs)
    llm_steps.append("mem0保存: 今回の会話を長期記憶へ保存")
    return response


def run_deep_agent_only_when_needed(
    *,
    reason: str,
    question: str,
    image_payloads: list[dict[str, str]],
    force_rebuild: bool,
    llm_steps: list[str],
):
    if reason == "missing_data":
        llm_steps.append("Deep Agent必要判定: RAGデータが未準備")
        spinner_text = "RAGデータが不足しているため、Deep Agentで自動収集してから回答します..."
    else:
        llm_steps.append("Deep Agent必要判定: RAG文脈が不十分")
        spinner_text = "ベクトルDBに十分な情報がないため、Deep Agentで自動収集してから回答します..."

    llm_steps.append("Deep Agent検索計画: 必要時のみ実行")
    with st.spinner(spinner_text):
        result, response = run_chat_deep_agent_answer(
            question=build_image_prompt_text(question, image_payloads),
            force_rebuild=force_rebuild,
            load_current_chatbot=lambda rebuild: load_chatbot(rebuild, "openrouter"),
        )
    return result, response



def render_openrouter_rag_chat(force_rebuild: bool) -> None:
    render_section_intro("RAGチャット", "保存済みレシピ参照を優先して検索し、必要なときだけ追加調査へ進みます。")
    render_status_cards(
        [
            ("Model", active_openrouter_model_label()),
            ("Retrieval", "Recipe RAG"),
            ("Question limit", f"{chat_turns_remaining('messages')} / {MAX_CHAT_TURNS}"),
        ]
    )
    if st.session_state.get("conversation_save_error"):
        st.warning("直近の会話はPostgreSQLへ保存できなかったため、ローカル退避履歴に保存しています。")
        show_postgres_recovery_hint()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if render_pending_deep_agent_job():
        return

    pending_permission = st.session_state.get("openrouter_rag_deep_agent_pending")
    if pending_permission:
        render_deep_agent_permission_buttons(
            pending_permission["question"],
            key_prefix="rag_pending_deep_agent",
            image_payloads=pending_permission.get("image_payloads") or [],
        )
        return

    pending_task = st.session_state.get("openrouter_pending_task")
    rerun_after_response = False
    if pending_task and pending_task.get("type") in {"openrouter_rag", "openrouter_rag_deep_agent_choice"}:
        rerun_after_response = True
        if pending_task.get("needs_model_switch"):
            render_openrouter_model_switch(pending_task)
        question = pending_task["question"]
        task_type = pending_task["type"]
        choice = pending_task.get("choice")
        image_payloads = pending_task.get("image_payloads") or []
        st.session_state.openrouter_pending_task = None
    else:
        question = None
        task_type = "openrouter_rag"
        choice = None
        image_payloads = []
    llm_steps: list[str] = []

    image_files = render_image_input("rag")
    can_chat = render_turn_limit("messages")
    if question is None and (
        user_text := st.chat_input(
            "例: 豚汁の材料と作り方、普通の味噌汁との違いを教えて",
            disabled=not can_chat,
        )
    ):
        image_payloads = prepare_image_payloads(image_files)
        question = user_text
        display_question = question
        if image_payloads:
            display_question += "\n\n画像: " + ", ".join(image["name"] for image in image_payloads)
        st.session_state.messages.append({"role": "user", "content": display_question})
        st.session_state.openrouter_rag_turn_count = count_user_turns(st.session_state.messages)
        persist_current_conversation(
            ai_type="OpenRouter_RAG",
            messages_key="messages",
            conversation_key="openrouter_rag_conversation_id",
        )
        with st.chat_message("user"):
            st.markdown(question)
            for image_file in image_files:
                st.image(image_file, caption=getattr(image_file, "name", "image"), use_container_width=True)

    if question is None:
        return

    if task_type == "openrouter_rag_deep_agent_choice":
        with st.chat_message("assistant"):
            try:
                if choice:
                    with st.spinner("Deep Agentで情報を探して保存し、RAGインデックスを再作成しています..."):
                        result, response = run_chat_deep_agent_answer(
                            question=build_image_prompt_text(question, image_payloads),
                            force_rebuild=True,
                            load_current_chatbot=lambda rebuild: load_chatbot(rebuild, "openrouter"),
                        )
                    if result is None and response is None:
                        st.info("Deep Agent Cloud Run Jobを開始しました。完了後に「状態を更新して回答を続ける」を押してください。")
                        st.stop()
                    prefix = f"Deep Agentで{len(result.saved_pages)}件の参照を保存しました。\n\n"
                else:
                    denial = deep_agent_denied_message(question)
                    st.markdown(denial)
                    st.session_state.messages.append({"role": "assistant", "content": denial})
                    persist_current_conversation(
                        ai_type="OpenRouter_RAG",
                        messages_key="messages",
                        conversation_key="openrouter_rag_conversation_id",
                    )
                    st.stop()
            except Exception as exc:
                defer_for_openrouter_model_switch(
                    exc,
                    {
                        "type": "openrouter_rag_deep_agent_choice",
                        "question": question,
                        "choice": choice,
                        "image_payloads": image_payloads,
                    },
                )
                log_error("OpenRouter RAG Deep Agent choice handling", exc, details=f"question={question}")
                error_message = "OpenRouter RAG回答生成中にエラーが発生しました。"
                show_generation_error(exc, error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})
                persist_current_conversation(
                    ai_type="OpenRouter_RAG",
                    messages_key="messages",
                    conversation_key="openrouter_rag_conversation_id",
                )
                st.stop()
            stream_markdown_text(prefix + response.answer)
            render_sources(response.sources)
        st.session_state.rebuild_index_next = False
        st.session_state.messages.append({"role": "assistant", "content": prefix + response.answer})
        persist_current_conversation(
            ai_type="OpenRouter_RAG",
            messages_key="messages",
            conversation_key="openrouter_rag_conversation_id",
        )
        if rerun_after_response:
            st.rerun()
        return

    should_rebuild = force_rebuild or st.session_state.get("rebuild_index_next", False)
    with st.chat_message("assistant"):
        try:
            llm_steps.append("RAG準備確認: 保存済みデータ/indexの状態を確認")
            if not recipe_knowledge_ready(should_rebuild):
                result, response = run_deep_agent_only_when_needed(
                    reason="missing_data",
                    question=question,
                    image_payloads=image_payloads,
                    force_rebuild=True,
                    llm_steps=llm_steps,
                )
                if result is None and response is None:
                    st.info("Deep Agent Cloud Run Jobを開始しました。完了後に「状態を更新して回答を続ける」を押してください。")
                    render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
                    st.stop()
                llm_steps.append(f"Deep Agent保存: {len(result.saved_pages)}件")
                llm_steps.append("RAG回答生成: Deep Agent収集後の文脈で実行")
                prefix = f"Deep Agentで{len(result.saved_pages)}件の参照を保存しました。\n\n"
                stream_markdown_text(prefix + response.answer)
                render_sources(response.sources)
                render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
                st.session_state.rebuild_index_next = False
                st.session_state.messages.append({"role": "assistant", "content": prefix + response.answer})
                persist_current_conversation(
                    ai_type="OpenRouter_RAG",
                    messages_key="messages",
                    conversation_key="openrouter_rag_conversation_id",
                )
                return

            with st.spinner("RAG chatbotを準備しています..."):
                llm_steps.append("RAG準備: chatbot/indexを読み込み")
                chatbot = load_openrouter_rag_chatbot_for_question(should_rebuild)

            with st.spinner("レシピページを検索して、RAGで十分に答えられるか判定中..."):
                _, docs, has_context = retrieve_and_assess_openrouter_context(
                    chatbot=chatbot,
                    question=question,
                    image_payloads=image_payloads,
                    llm_steps=llm_steps,
                )

            if not has_context:
                llm_steps.append("RAG context判定結果: 不十分")
                result, response = run_deep_agent_only_when_needed(
                    reason="insufficient_context",
                    question=question,
                    image_payloads=image_payloads,
                    force_rebuild=True,
                    llm_steps=llm_steps,
                )
                if result is None and response is None:
                    st.info("Deep Agent Cloud Run Jobを開始しました。完了後に「状態を更新して回答を続ける」を押してください。")
                    render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
                    st.stop()
                llm_steps.append(f"Deep Agent保存: {len(result.saved_pages)}件")
                llm_steps.append("RAG回答生成: Deep Agent収集後の文脈で実行")
                prefix = f"Deep Agentで{len(result.saved_pages)}件の参照を保存しました。\n\n"
                stream_markdown_text(prefix + response.answer)
                render_sources(response.sources)
                render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
                st.session_state.rebuild_index_next = False
                st.session_state.messages.append({"role": "assistant", "content": prefix + response.answer})
                persist_current_conversation(
                    ai_type="OpenRouter_RAG",
                    messages_key="messages",
                    conversation_key="openrouter_rag_conversation_id",
                )
                return

            with st.spinner("RAG文脈を使ってOpenRouter free modelで回答を作成中..."):
                response = create_openrouter_rag_response(
                    chatbot=chatbot,
                    question=question,
                    docs=docs,
                    image_payloads=image_payloads,
                    llm_steps=llm_steps,
                )
        except RuntimeError as exc:
            defer_for_openrouter_model_switch(
                exc,
                {
                    "type": "openrouter_rag",
                    "question": question,
                    "image_payloads": image_payloads,
                },
            )
            if "Deep Agent" in "\n".join(llm_steps):
                details = format_rate_limit_details(exc, "Deep Agent automatic collection")
                log_error("OpenRouter RAG Deep Agent automatic collection", exc, details=f"question={question}\n{details}")
                render_deep_agent_failure(exc, question=question)
                render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
                st.session_state.messages.append({"role": "assistant", "content": "Deep Agent自動収集に失敗しました。"})
                persist_current_conversation(
                    ai_type="OpenRouter_RAG",
                    messages_key="messages",
                    conversation_key="openrouter_rag_conversation_id",
                )
            else:
                show_recipe_source_error(exc)
            st.stop()
        except Exception as exc:
            defer_for_openrouter_model_switch(
                exc,
                {
                    "type": "openrouter_rag",
                    "question": question,
                    "image_payloads": image_payloads,
                },
            )
            details = format_rate_limit_details(exc, "OpenRouter RAG chat")
            log_error("OpenRouter RAG chat response generation", exc, details=f"question={question}\n{details}")
            error_message = "OpenRouter RAG回答生成中にエラーが発生しました。"
            if "Deep Agent" in "\n".join(llm_steps):
                render_deep_agent_failure(exc, question=question)
            else:
                show_generation_error(exc, error_message)
            render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            persist_current_conversation(
                ai_type="OpenRouter_RAG",
                messages_key="messages",
                conversation_key="openrouter_rag_conversation_id",
            )
            st.stop()
        stream_markdown_text(response.answer)
        render_sources(response.sources)
        render_llm_trace("今回のLLM/ツール実行段階", llm_steps)
    st.session_state.messages.append({"role": "assistant", "content": response.answer})
    persist_current_conversation(
        ai_type="OpenRouter_RAG",
        messages_key="messages",
        conversation_key="openrouter_rag_conversation_id",
    )
    if rerun_after_response:
        st.rerun()


def render_openrouter_chat() -> None:
    from app.openrouter_chatbot import ask_openrouter, ask_openrouter_multimodal

    render_section_intro("クイック相談", "RAGを使わず、献立の方向性や下ごしらえの確認を軽く相談できます。")
    render_status_cards(
        [
            ("Model", active_openrouter_model_label()),
            ("Retrieval", "Off"),
            ("Question limit", f"{chat_turns_remaining('openrouter_messages')} / {MAX_CHAT_TURNS}"),
        ]
    )
    if st.session_state.get("conversation_save_error"):
        st.warning("直近の会話はPostgreSQLへ保存できなかったため、ローカル退避履歴に保存しています。")
        show_postgres_recovery_hint()

    for message in st.session_state.openrouter_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_task = st.session_state.get("openrouter_pending_task")
    rerun_after_response = False
    if pending_task and pending_task.get("type") == "openrouter_chat":
        rerun_after_response = True
        if pending_task.get("needs_model_switch"):
            render_openrouter_model_switch(pending_task)
        question = pending_task["question"]
        image_payloads = pending_task.get("image_payloads") or []
        st.session_state.openrouter_pending_task = None
    else:
        image_files = render_image_input("openrouter")
        can_chat = render_turn_limit("openrouter_messages")
        if question := st.chat_input("例: だし巻き卵の作り方を説明して", disabled=not can_chat):
            image_payloads = prepare_image_payloads(image_files)
            display_question = question
            if image_payloads:
                display_question += "\n\n画像: " + ", ".join(image["name"] for image in image_payloads)
            st.session_state.openrouter_messages.append({"role": "user", "content": display_question})
            st.session_state.openrouter_turn_count = count_user_turns(st.session_state.openrouter_messages)
        else:
            return
        persist_current_conversation(
            ai_type="OpenRouter",
            messages_key="openrouter_messages",
            conversation_key="openrouter_conversation_id",
        )
        with st.chat_message("user"):
            st.markdown(question)
            for image_file in image_files:
                st.image(image_file, caption=getattr(image_file, "name", "image"), use_container_width=True)

    with st.chat_message("assistant"):
        try:
            with st.spinner("OpenRouter free modelに問い合わせ中..."):
                if image_payloads:
                    answer = ask_openrouter_multimodal(build_multimodal_content(question, image_payloads))
                else:
                    answer = ask_openrouter(question)
        except Exception as exc:
            defer_for_openrouter_model_switch(
                exc,
                {
                    "type": "openrouter_chat",
                    "question": question,
                    "image_payloads": image_payloads,
                },
            )
            log_error("OpenRouter-only chat generation", exc, details=f"question={question}")
            error_message = "OpenRouter単体チャットの回答生成中にエラーが発生しました。"
            show_generation_error(exc, error_message)
            st.session_state.openrouter_messages.append({"role": "assistant", "content": error_message})
            persist_current_conversation(
                ai_type="OpenRouter",
                messages_key="openrouter_messages",
                conversation_key="openrouter_conversation_id",
            )
            st.stop()
        stream_markdown_text(answer)
    st.session_state.openrouter_messages.append({"role": "assistant", "content": answer})
    persist_current_conversation(
        ai_type="OpenRouter",
        messages_key="openrouter_messages",
        conversation_key="openrouter_conversation_id",
    )
    if rerun_after_response:
        st.rerun()


def render_crawl4ai_check() -> None:
    # crawl4aiの検索クエリ生成、URL発見、LLM抽出、処理時間を確認するページです。
    from app.crawl4ai_performance import run_crawl4ai_performance_check

    render_section_intro("抽出チェック", "検索、候補URL選定、crawl4ai抽出の品質と処理時間を確認します。")
    render_status_cards(
        [
            ("Mode", "Quality check"),
            ("Model policy", "Free only"),
            ("Output", "Extraction report"),
        ]
    )
    user_request = st.text_area(
        "欲しい情報",
        "OpenRouterのfree model一覧と使い分けを知りたい",
        height=100,
    )
    max_results = st.slider("検索候補URL数", min_value=1, max_value=8, value=5)
    if st.button("Crawl4AI性能チェックを実行", type="primary"):
        progress_box = st.container()
        progress_lines: list[str] = []

        def show_progress(message: str) -> None:
            progress_lines.append(message)
            progress_box.markdown("\n\n".join(f"- {line}" for line in progress_lines))

        with st.spinner("検索クエリ生成、URL探索、crawl4ai LLM抽出を実行中..."):
            result = run_crawl4ai_performance_check(
                user_request,
                max_results=max_results,
                progress_callback=show_progress,
            )
        if result.search_query:
            st.write("Generated search query")
            st.code(result.search_query)
        if result.candidate_urls:
            st.write("Search results")
            st.dataframe(
                [{"rank": index + 1, "url": url} for index, url in enumerate(result.candidate_urls)],
                use_container_width=True,
                hide_index=True,
            )
        if not result.success:
            log_error(
                "Crawl4AI performance check",
                RuntimeError(result.error or "unknown error"),
                details=(
                    f"model={result.model_id}\n"
                    f"selected_url={result.selected_url}\n"
                    f"attempted_urls={result.attempted_urls}\n"
                    f"rate_limit={result.rate_limited}\n"
                    f"extraction_mode={result.extraction_mode}"
                ),
            )
            st.error("Crawl4AI性能チェックに失敗しました。")
            st.code(result.error or "unknown error")
            if result.timings:
                st.json(result.timings)
            return

        st.success("Crawl4AI性能チェックが完了しました。")
        if result.rate_limited:
            st.warning("OpenRouter free model制限に達したため、LLM抽出ではなく通常抽出で表示しました。")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total sec", f"{result.timings.get('total_sec', 0):.2f}")
        col_b.metric("Markdown chars", result.markdown_chars)
        col_c.metric("HTML chars", result.cleaned_html_chars)
        col_model, col_mode = st.columns(2)
        col_model.metric("OpenRouter model", result.model_id or "-")
        col_mode.metric("Extraction mode", result.extraction_mode)

        st.write("Selected URL")
        st.code(result.selected_url)
        if result.fallback_reason:
            with st.expander("Fallback reason"):
                st.code(result.fallback_reason)

        with st.expander("Attempted URLs"):
            st.json(result.attempted_urls)
        if result.progress_messages:
            with st.expander("AI thinking process", expanded=True):
                for line in result.progress_messages:
                    st.write(line)
        with st.expander("Timing details", expanded=True):
            st.json({key: round(value, 3) for key, value in result.timings.items()})
        st.write("Extracted content")
        st.code(result.extracted_content, language="json")


def render_adaptive_crawl() -> None:
    # crawl4ai AdaptiveCrawlerで、サイト内リンクを辿りながら調査範囲を広げます。
    from app.adaptive_crawler import adaptive_architecture_preview, run_adaptive_site_research

    render_section_intro("サイト調査", "サイト内URLを段階的に辿り、調査クエリに対して十分な材料が集まるまで探索します。")
    render_status_cards(
        [
            ("Crawler", "Adaptive"),
            ("Scope", "Site links"),
            ("Output", "Research synthesis"),
        ]
    )

    start_url = st.text_input("開始URL", value="https://www.justonecookbook.com/")
    query = st.text_area(
        "調査クエリ",
        "omurice recipe techniques, ingredients, variations, and serving notes",
        height=90,
    )
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        max_pages = st.slider("最大ページ数", min_value=3, max_value=30, value=12)
        strategy = st.selectbox("探索戦略", ["statistical", "embedding"], index=0)
    with col_b:
        max_depth = st.slider("最大深さ", min_value=1, max_value=6, value=3)
        top_k_links = st.slider("各ページで辿るリンク数", min_value=1, max_value=8, value=3)
    with col_c:
        confidence_threshold = st.slider("停止信頼度", min_value=0.3, max_value=0.95, value=0.75, step=0.05)
        top_k_content = st.slider("LLM統合対象ページ数", min_value=1, max_value=10, value=6)

    with st.expander("System architecture preview", expanded=False):
        st.json(
            adaptive_architecture_preview(
                start_url=start_url,
                query=query,
                strategy=strategy,
                max_pages=max_pages,
                max_depth=max_depth,
                top_k_links=top_k_links,
                confidence_threshold=confidence_threshold,
            )
        )

    if st.button("Adaptive Crawlを実行", type="primary"):
        try:
            with st.spinner("Adaptive Crawlingでサイト内調査を実行中..."):
                result = run_adaptive_site_research(
                    start_url=start_url,
                    query=query,
                    max_pages=max_pages,
                    max_depth=max_depth,
                    top_k_links=top_k_links,
                    confidence_threshold=confidence_threshold,
                    strategy=strategy,
                    top_k_content=top_k_content,
                )
        except Exception as exc:
            log_error("Crawl4AI adaptive site research", exc, details=f"start_url={start_url}, query={query}")
            st.error("Adaptive Crawlに失敗しました。設定、ネットワーク、OpenRouterの状態を確認してください。")
            st.code(str(exc))
            return

        st.success("Adaptive Crawlが完了しました。")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Confidence", f"{result.confidence:.0%}")
        col_b.metric("Crawled pages", len(result.crawled_urls))
        col_c.metric("Total sec", f"{result.timings.get('total_sec', 0):.2f}")

        st.write("LLM synthesis")
        st.markdown(result.synthesis)

        with st.expander("Relevant pages", expanded=True):
            for page in result.relevant_pages:
                st.markdown(f"**{page.title}**")
                st.caption(f"{page.url} / score={page.score:.3f}")
                st.code(page.content[:1400])

        with st.expander("Crawled URLs"):
            st.json(result.crawled_urls)
        with st.expander("Saved files"):
            st.json(
                {
                    "output_dir": str(result.output_dir),
                    "knowledge_base": str(result.knowledge_base_path),
                    "result": str(result.result_path),
                }
            )
        with st.expander("Architecture"):
            st.json(result.architecture)


def main() -> None:
    # Streamlitアプリ全体の入口です。sidebarで選んだmodeに応じて表示ページを切り替えます。
    apply_styles()
    force_rebuild, mode = render_sidebar()
    ensure_chat_history()
    ensure_openrouter_chat_history()
    render_app_header(mode)

    # サイドバーのradioで選ばれたモードごとに、描画関数を切り替えます。
    if mode == "OpenRouter RAG Chat":
        render_openrouter_rag_chat(force_rebuild)
    elif mode == "OpenRouter Chat":
        render_openrouter_chat()
    elif mode == "past conversation":
        render_past_conversation()
    elif mode == "Crawl4AI Check":
        render_crawl4ai_check()
    else:
        render_adaptive_crawl()


try:
    main()
except Exception as exc:
    # 最後の安全網です。個別のtry/exceptで拾えなかったUIエラーをログに残します。
    log_error("Unhandled Streamlit UI error", exc)
    st.error("予期しないエラーが発生しました。開発者向けログに記録しました。")
    with st.expander("エラー詳細"):
        st.code(str(exc))
