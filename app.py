from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

try:
    from app.config import GOOGLE_API_KEY, LOCAL_RECIPE_DIR, VECTOR_INDEX_DIR
except ImportError:
    fallback_data_dir = Path(__file__).resolve().parent / "data"
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    VECTOR_INDEX_DIR = fallback_data_dir / "turbovec_index"
    LOCAL_RECIPE_DIR = fallback_data_dir / "joc_pages"

try:
    from app.error_logger import log_error
except ImportError:
    def log_error(context: str, error: BaseException, details: str | None = None) -> None:
        error_log_path = Path(__file__).resolve().parent / "ERROR_LOG.md"
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        error_log_path.open("a", encoding="utf-8").write(
            f"\n## Import-time logging fallback\n\n"
            f"- Context: {context}\n"
            f"- Error Type: {type(error).__name__}\n"
            f"- Message: {error}\n"
            f"- Details: {details or ''}\n"
        )


st.set_page_config(page_title="Recipe RAG Chatbot", page_icon="🍱", layout="wide")


@st.cache_resource(show_spinner="Loading recipe knowledge base...")
def load_chatbot(force_rebuild_index: bool = False):
    from app.rag_chatbot import RecipeRAGChatbot

    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index)


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1160px; padding-top: 1.4rem; }
        [data-testid="stSidebar"] { background: #f7f3ed; }
        .source-chip {
            display: inline-block; padding: 0.2rem 0.5rem; margin: 0.1rem;
            border: 1px solid #dfd6c7; border-radius: 999px; font-size: 0.78rem;
            color: #5f5141; background: #fffaf2;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_recipe_source_error(exc: Exception) -> None:
    log_error("Recipe source loading", exc)
    if is_gemini_key_error(exc):
        show_gemini_key_error(exc)
        return

    st.error("RAG用のレシピ文書を読み込めませんでした。")
    st.info(
        "Just One CookbookがPythonからの自動取得に403を返している可能性があります。"
        f"ブラウザで保存したレシピページの `.html`, `.txt`, `.md` を `{LOCAL_RECIPE_DIR}` に入れて、"
        "`python scripts/rebuild_index.py` を実行してください。"
    )
    with st.expander("詳細エラー"):
        st.code(str(exc))


def is_gemini_key_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "GOOGLE_API_KEY" in message
        or "GEMINI_API_KEY" in message
        or "API key was reported as leaked" in message
        or "PERMISSION_DENIED" in message
    )


def show_gemini_key_error(exc: Exception) -> None:
    message = str(exc)
    if "reported as leaked" in message:
        st.error("Gemini API keyが漏洩済みとして拒否されました。")
        st.info(
            "Google AI Studioで新しいAPI keyを再発行し、`.env` の `GOOGLE_API_KEY` を更新してください。"
            "更新後に `docker compose -f docker/docker-compose.yml up -d` を実行すると、コンテナへ反映されます。"
        )
    else:
        st.error("Gemini API keyが設定されていない、または利用できません。")
        st.info(
            "RAGの回答生成にはGemini 2.5 Flashを使います。"
            "`.env` に `GOOGLE_API_KEY=...` を設定してから `docker compose -f docker/docker-compose.yml up -d` を実行してください。"
        )
    with st.expander("詳細エラー"):
        st.code(message)


def show_generation_error(exc: Exception, fallback_message: str) -> None:
    if is_gemini_key_error(exc):
        show_gemini_key_error(exc)
        return

    st.error(fallback_message)
    with st.expander("エラー詳細"):
        st.code(str(exc))


def has_local_recipe_files() -> bool:
    if not LOCAL_RECIPE_DIR.exists():
        return False
    return any(
        path.is_file() and path.suffix.lower() in {".html", ".htm", ".txt", ".md"}
        for path in LOCAL_RECIPE_DIR.iterdir()
    )


def has_vector_index() -> bool:
    return VECTOR_INDEX_DIR.exists() and any(VECTOR_INDEX_DIR.iterdir())


def recipe_knowledge_ready(force_rebuild: bool) -> bool:
    if force_rebuild:
        return has_local_recipe_files()
    return has_vector_index() or has_local_recipe_files()


def show_missing_recipe_data_message() -> None:
    st.warning("RAGに使えるレシピデータがまだありません。")
    st.info(
        "左サイドバーの「ページをdataに保存」からJust One CookbookのレシピURLを保存してください。"
        f"保存先は `{LOCAL_RECIPE_DIR}` です。"
    )


def render_sidebar() -> tuple[bool, str]:
    from app.scraper import run_deep_agent_recipe_collection, save_recipe_page_from_url

    with st.sidebar:
        st.title("Recipe RAG")
        st.caption("Just One Cookbookを検索して、和食レシピ推論に特化して回答します。")
        force_rebuild = st.button("RAGインデックスを再作成")
        mode = st.radio("モード", ["Chat", "JSON + PostgreSQL", "DB DataFrame"], label_visibility="collapsed")
        st.divider()

        with st.expander("ページをdataに保存", expanded=True):
            recipe_url = st.text_input("Recipe URL", placeholder="https://www.justonecookbook.com/tonjiru/")
            if st.button("URLを保存", use_container_width=True):
                if not recipe_url:
                    st.warning("保存したいURLを入力してください。")
                else:
                    try:
                        saved = save_recipe_page_from_url(recipe_url)
                        load_chatbot.clear()
                        st.session_state.rebuild_index_next = True
                        st.success(f"保存しました: {saved.path.name} ({saved.text_chars} chars)")
                        st.caption("次回のChat/JSON実行時にRAGインデックスを自動で再作成します。")
                    except Exception as exc:
                        log_error("Sidebar URL save", exc, details=f"recipe_url={recipe_url}")
                        st.error("ページを保存できませんでした。403の場合はサイト側が自動取得を拒否しています。")
                        st.code(str(exc))

        with st.expander("Deep Agent自動収集"):
            st.warning("Deep Agent収集はLLMと複数回のWeb取得を使うため、数分かかることがあります。")
            deep_agent_unavailable = sys.version_info < (3, 11) or not GOOGLE_API_KEY
            if sys.version_info < (3, 11):
                st.caption("Deep AgentsはPython 3.11以上が必要です。現在の環境では通常のURL保存を使ってください。")
            elif not GOOGLE_API_KEY:
                st.caption("Deep Agentsを使うには `.env` に `GOOGLE_API_KEY` が必要です。")
            else:
                st.caption("Deep Agentsを実行できます。完了まで数分かかることがあります。")
            deep_query = st.text_input("収集したいレシピ", placeholder="tonjiru miso soup")
            deep_max_pages = st.slider("最大保存ページ数", min_value=1, max_value=5, value=3)
            if st.button("Deep Agentで収集", use_container_width=True, disabled=deep_agent_unavailable):
                if not deep_query:
                    st.warning("収集したいレシピ名やテーマを入力してください。")
                else:
                    with st.spinner("Deep Agentが関連ページを探して保存しています。時間がかかります..."):
                        try:
                            saved_pages = run_deep_agent_recipe_collection(deep_query, max_pages=deep_max_pages)
                            load_chatbot.clear()
                            st.session_state.rebuild_index_next = True
                            st.success(f"{len(saved_pages)}件保存しました。")
                            for saved_page in saved_pages:
                                st.caption(f"{saved_page.path.name} - {saved_page.url}")
                        except Exception as exc:
                            log_error(
                                "Sidebar Deep Agent collection",
                                exc,
                                details=f"query={deep_query}, max_pages={deep_max_pages}",
                            )
                            st.error("Deep Agent収集に失敗しました。設定やネットワーク状態を確認してください。")
                            st.code(str(exc))

    return force_rebuild, mode


def ensure_chat_history() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "こんにちは。Just One Cookbookの情報を元に、和食レシピを一緒に組み立てます。",
            }
        ]


def render_chat(force_rebuild: bool) -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("例: 豚汁の材料と作り方、普通の味噌汁との違いを教えて"):
        should_rebuild = force_rebuild or st.session_state.get("rebuild_index_next", False)
        if not recipe_knowledge_ready(should_rebuild):
            show_missing_recipe_data_message()
            st.stop()
        try:
            chatbot = load_chatbot(should_rebuild)
            st.session_state.rebuild_index_next = False
        except RuntimeError as exc:
            show_recipe_source_error(exc)
            st.stop()

        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("レシピページを検索して回答を作成中..."):
                    response = chatbot.answer(question)
            except Exception as exc:
                log_error(
                    "Chat conversation response generation",
                    exc,
                    details=f"question={question}",
                )
                error_message = "回答生成中にエラーが発生しました。開発者向けログに記録しました。"
                show_generation_error(exc, error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})
                st.stop()
            st.markdown(response.answer)
            if response.sources:
                st.caption("Sources")
                st.markdown(
                    " ".join(f'<span class="source-chip">{url}</span>' for url in response.sources),
                    unsafe_allow_html=True,
                )
        st.session_state.messages.append({"role": "assistant", "content": response.answer})


def render_json_mode(force_rebuild: bool) -> None:
    from app.json_output import generate_recipe_json

    st.subheader("Structured recipe JSON")
    question = st.text_area(
        "レシピ要望",
        "Please share a healthier high-protein version of dashi-maki tamago.",
        height=100,
    )
    if st.button("JSONを生成してDBに保存", type="primary"):
        with st.spinner("RAG検索、JSON生成、PostgreSQL保存を実行中..."):
            try:
                should_rebuild = force_rebuild or st.session_state.get("rebuild_index_next", False)
                if not recipe_knowledge_ready(should_rebuild):
                    show_missing_recipe_data_message()
                    st.stop()
                if should_rebuild:
                    load_chatbot.clear()
                result = generate_recipe_json(question, save_to_db=True, force_rebuild_index=should_rebuild)
                st.session_state.rebuild_index_next = False
            except RuntimeError as exc:
                log_error("JSON generation", exc, details=f"question={question}")
                show_recipe_source_error(exc)
                st.stop()
            except Exception as exc:
                log_error("JSON generation", exc, details=f"question={question}")
                show_generation_error(exc, "JSON生成中にエラーが発生しました。開発者向けログに記録しました。")
                st.stop()
        st.success(f"Saved to PostgreSQL. id={result.get('database_id')}")
        st.json(result)


def render_dataframe_mode() -> None:
    from app.view_db_dataframe import recipes_dataframe

    st.subheader("PostgreSQL contents")
    try:
        df = recipes_dataframe()
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as exc:
        log_error("DB DataFrame view", exc)
        st.error(f"DBを読み込めませんでした: {exc}")


def main() -> None:
    apply_styles()
    force_rebuild, mode = render_sidebar()
    ensure_chat_history()
    st.title("Recipe Inference RAG Chatbot")

    if mode == "Chat":
        render_chat(force_rebuild)
    elif mode == "JSON + PostgreSQL":
        render_json_mode(force_rebuild)
    else:
        render_dataframe_mode()


try:
    main()
except Exception as exc:
    log_error("Unhandled Streamlit UI error", exc)
    st.error("予期しないエラーが発生しました。開発者向けログに記録しました。")
    with st.expander("エラー詳細"):
        st.code(str(exc))
