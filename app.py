from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

try:
    from app.config import (
        DEEP_AGENT_LLM_BACKEND,
        GOOGLE_API_KEY,
        LOCAL_RECIPE_DIR,
        QWEN_BASE_URL,
        QWEN_MODEL,
        VECTOR_INDEX_DIR,
        WEB_RECIPE_REFERENCE_DIR,
    )
except ImportError:
    # config.pyのimport前に壊れても、Streamlit画面とログ出力を最低限続けるためのfallbackです。
    fallback_data_dir = Path(__file__).resolve().parent / "data"
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:11434/v1")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3:4b")
    DEEP_AGENT_LLM_BACKEND = os.getenv("DEEP_AGENT_LLM_BACKEND", os.getenv("MAIN_LLM_BACKEND", "qwen")).lower()
    VECTOR_INDEX_DIR = fallback_data_dir / "turbovec_index"
    LOCAL_RECIPE_DIR = fallback_data_dir / "joc_pages"
    WEB_RECIPE_REFERENCE_DIR = fallback_data_dir / "web_recipe_reference"

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
st.set_page_config(page_title="Recipe RAG Chatbot", page_icon="🍱", layout="wide")


@st.cache_resource(show_spinner="Loading recipe knowledge base...")
def load_chatbot(force_rebuild_index: bool = False, llm_backend: str | None = None):
    # RAG chatbotの初期化はembedding/index読み込みが重いため、Streamlitのresource cacheに載せます。
    # load_chatbot.clear() を呼ぶと、次回アクセス時にindexを再読み込み・再構築できます。
    from app.rag_chatbot import RecipeRAGChatbot

    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index, llm_backend=llm_backend)


@st.cache_resource(show_spinner="Loading Qwen RAG chatbot...")
def load_qwen_chatbot(force_rebuild_index: bool = False):
    # Qwen専用RAGも同じRAG indexを使いますが、LLM指定が別なので通常RAGとは別cacheにします。
    from app.qwen import QwenRAGChatbot

    return QwenRAGChatbot(force_rebuild_index=force_rebuild_index)


def apply_styles() -> None:
    # 画面全体の幅、サイドバー色、source表示用chipだけをCSSで軽く整えます。
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
    # RAG用データの読み込みに失敗した時の専用エラー表示です。
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
    # Gemini APIキー由来のエラーかどうかを文字列でざっくり判定します。
    message = str(exc)
    return (
        "GOOGLE_API_KEY" in message
        or "GEMINI_API_KEY" in message
        or "API key was reported as leaked" in message
        or "PERMISSION_DENIED" in message
    )


def show_gemini_key_error(exc: Exception) -> None:
    # Gemini APIキー不足・漏洩済み・権限エラーの時に、ユーザーが次に取る行動を表示します。
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
    # Chat/JSON/Gemini回答生成で共通利用するエラー表示です。
    if is_gemini_key_error(exc):
        show_gemini_key_error(exc)
        return

    st.error(fallback_message)
    with st.expander("エラー詳細"):
        st.code(str(exc))


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


def has_vector_index() -> bool:
    # TurboVec indexがすでに作成済みか確認します。
    return VECTOR_INDEX_DIR.exists() and any(VECTOR_INDEX_DIR.iterdir())


def recipe_knowledge_ready(force_rebuild: bool) -> bool:
    # RAG実行前の準備確認です。
    # 再構築する場合は元データが必要で、再構築しない場合は既存indexだけでも動けます。
    if force_rebuild:
        return has_local_recipe_files()
    return has_vector_index() or has_local_recipe_files()


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
        st.title("Recipe RAG")
        st.caption("保存済みレシピ参照を検索して、和食レシピ推論に特化して回答します。")
        # このボタンを押した場合、次回RAG実行時に既存indexではなく文書から作り直します。
        force_rebuild = st.button("RAGインデックスを再作成")
        # このradioがメイン画面の「ページ切り替え」として働きます。
        mode = st.radio(
            "モード",
            [
                "Qwen RAG Chat",
                "Gemini RAG Chat",
                "Qwen Chat",
                "Gemini Chat",
                "Crawl4AI Check",
                "Adaptive Crawl",
                "JSON + PostgreSQL",
                "DB DataFrame",
            ],
            label_visibility="collapsed",
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
                        load_qwen_chatbot.clear()
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
            deep_agent_unavailable = DEEP_AGENT_LLM_BACKEND in {"gemini", "google"} and not GOOGLE_API_KEY
            if deep_agent_unavailable:
                st.caption("GeminiでDeep Agentを使うには `.env` に `GOOGLE_API_KEY` が必要です。")
            else:
                st.caption(
                    f"LLM: `{DEEP_AGENT_LLM_BACKEND}`。"
                    f"Web検索、seed URL選択、crawl4ai deep crawl、保存を実行します。保存先: `{WEB_RECIPE_REFERENCE_DIR}`"
                )
            deep_query = st.text_input("収集したいレシピ/調査テーマ", placeholder="omurice recipe technique and variations")
            deep_max_pages = st.slider("最大保存ページ数", min_value=1, max_value=5, value=3)
            if st.button("Deep Agentで収集", use_container_width=True, disabled=deep_agent_unavailable):
                if not deep_query:
                    st.warning("収集したいレシピ名やテーマを入力してください。")
                else:
                    with st.spinner("Agentic CrawlerがWeb上の関連ページを調査して保存しています。時間がかかります..."):
                        try:
                            result = run_deep_agent_recipe_collection_with_details(
                                deep_query,
                                max_pages=deep_max_pages,
                            )
                            # Deep Agentが保存したページもRAGの新規材料なので、cacheを消して再構築予約します。
                            load_chatbot.clear()
                            load_qwen_chatbot.clear()
                            st.session_state.rebuild_index_next = True
                            st.success(f"{len(result.saved_pages)}件保存しました。")
                            st.caption(result.notes)
                            with st.expander("Deep Agentの実行内容"):
                                # デバッグしやすいよう、Agentが考えた検索語と選んだseed URLをUIに出します。
                                st.write("Search queries")
                                st.json(result.search_queries)
                                st.write("Selected URLs")
                                st.json(result.selected_urls)
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


def ensure_gemini_chat_history() -> None:
    # Gemini単体テスト用の履歴です。RAGチャットの履歴とは分けて管理します。
    if "gemini_messages" not in st.session_state:
        st.session_state.gemini_messages = [
            {
                "role": "assistant",
                "content": "こんにちは。RAGを使わず、Geminiだけで回答します。",
            }
        ]


def ensure_qwen_chat_history() -> None:
    # Ollama Qwen RAG用の会話履歴です。Gemini RAGとは分けて比較しやすくします。
    if "qwen_messages" not in st.session_state:
        st.session_state.qwen_messages = [
            {
                "role": "assistant",
                "content": "こんにちは。Ollama上のQwenを使い、同じRAG情報を元に回答します。",
            }
        ]


def ensure_qwen_only_chat_history() -> None:
    # Qwen単体テスト用の履歴です。RAGありのQwen履歴とは分けます。
    if "qwen_only_messages" not in st.session_state:
        st.session_state.qwen_only_messages = [
            {
                "role": "assistant",
                "content": "こんにちは。RAGを使わず、Ollama上のQwenだけで回答します。",
            }
        ]


def render_chat(force_rebuild: bool, llm_backend: str | None = None) -> None:
    # RAG Chatページです。保存済みレシピ文書を検索してから回答します。
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("例: 豚汁の材料と作り方、普通の味噌汁との違いを教えて"):
        # サイドバーの手動再構築、または新規ページ保存後の自動再構築フラグを反映します。
        should_rebuild = force_rebuild or st.session_state.get("rebuild_index_next", False)
        if not recipe_knowledge_ready(should_rebuild):
            show_missing_recipe_data_message()
            st.stop()
        try:
            chatbot = load_chatbot(should_rebuild, llm_backend)
            # chatbotの読み込みに成功したら、再構築予約は消します。
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
                    # ここでretriever検索、LLM回答生成、long-term memory保存が実行されます。
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
                # RAGで参照されたsourceをchip風に表示します。
                st.caption("Sources")
                st.markdown(
                    " ".join(f'<span class="source-chip">{url}</span>' for url in response.sources),
                    unsafe_allow_html=True,
                )
        st.session_state.messages.append({"role": "assistant", "content": response.answer})


def render_qwen_rag_chat(force_rebuild: bool) -> None:
    # Qwen RAG Chatページです。検索部分は共通で、回答生成にOllama Qwenを使います。
    st.subheader("Qwen RAG Chat")
    st.caption(f"Model: `{QWEN_MODEL}` / Base URL: `{QWEN_BASE_URL}`")

    for message in st.session_state.qwen_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("例: Qwenで、だし巻き卵の材料と作り方を説明して"):
        should_rebuild = force_rebuild or st.session_state.get("rebuild_index_next", False)
        if not recipe_knowledge_ready(should_rebuild):
            show_missing_recipe_data_message()
            st.stop()
        try:
            chatbot = load_qwen_chatbot(should_rebuild)
            st.session_state.rebuild_index_next = False
        except RuntimeError as exc:
            show_recipe_source_error(exc)
            st.stop()

        st.session_state.qwen_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("RAG検索後、Ollama Qwenで回答を作成中..."):
                    response = chatbot.answer(question)
            except Exception as exc:
                log_error("Qwen RAG chat response generation", exc, details=f"question={question}")
                error_message = (
                    "Qwen RAG回答生成中にエラーが発生しました。"
                    "Ollamaが起動しているか、`ollama run qwen3:4b` が動くか確認してください。"
                )
                show_generation_error(exc, error_message)
                st.session_state.qwen_messages.append({"role": "assistant", "content": error_message})
                st.stop()
            st.markdown(response.answer)
            if response.sources:
                st.caption("Sources")
                st.markdown(
                    " ".join(f'<span class="source-chip">{url}</span>' for url in response.sources),
                    unsafe_allow_html=True,
                )
        st.session_state.qwen_messages.append({"role": "assistant", "content": response.answer})


def render_qwen_chat() -> None:
    # Qwen単体テストページです。RAG、DB、mem0を通さずOllama Qwenだけを呼びます。
    from app.qwen import ask_qwen

    st.subheader("Qwen-only Chat")
    st.caption(f"RAGなし。Model: `{QWEN_MODEL}` / Base URL: `{QWEN_BASE_URL}`")

    for message in st.session_state.qwen_only_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("例: Qwenだけで、だし巻き卵の作り方を説明して"):
        st.session_state.qwen_only_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Ollama Qwenに直接問い合わせ中..."):
                    answer = ask_qwen(question)
            except Exception as exc:
                log_error("Qwen-only chat generation", exc, details=f"question={question}")
                error_message = (
                    "Qwen単体チャットの回答生成中にエラーが発生しました。"
                    "Ollamaが起動しているか、`ollama run qwen3:4b` が動くか確認してください。"
                )
                show_generation_error(exc, error_message)
                st.session_state.qwen_only_messages.append({"role": "assistant", "content": error_message})
                st.stop()
            st.markdown(answer)
        st.session_state.qwen_only_messages.append({"role": "assistant", "content": answer})


def render_gemini_chat() -> None:
    # Gemini単体テストページです。RAG、DB、mem0を通さずGemini APIだけを呼びます。
    from app.gemini_chatbot import ask_gemini

    st.subheader("Gemini-only Chat")
    st.caption("RAG、DB、long-term memoryを使わず、Gemini APIだけをテストします。")

    for message in st.session_state.gemini_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("例: Geminiだけで、だし巻き卵の作り方を説明して"):
        st.session_state.gemini_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Geminiに直接問い合わせ中..."):
                    # ask_geminiはretrieverを使わないので、Gemini API疎通確認に向いています。
                    answer = ask_gemini(question)
            except Exception as exc:
                log_error("Gemini-only chat generation", exc, details=f"question={question}")
                error_message = "Gemini単体チャットの回答生成中にエラーが発生しました。"
                show_generation_error(exc, error_message)
                st.session_state.gemini_messages.append({"role": "assistant", "content": error_message})
                st.stop()
            st.markdown(answer)
        st.session_state.gemini_messages.append({"role": "assistant", "content": answer})


def render_json_mode(force_rebuild: bool) -> None:
    # RAG検索結果を使って構造化JSONを作り、PostgreSQLへ保存するページです。
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
                    # 新しいローカル文書を反映するため、cache済みchatbotを破棄します。
                    load_chatbot.clear()
                    load_qwen_chatbot.clear()
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


def render_crawl4ai_check() -> None:
    # crawl4aiの検索クエリ生成、URL発見、LLM抽出、処理時間を確認するページです。
    from app.crawl4ai_performance import run_crawl4ai_performance_check

    st.subheader("Crawl4AI performance check")
    st.caption("URLを直接指定せず、ユーザー要望から検索クエリを作成して、候補URLを選び、crawl4aiでLLM抽出します。")
    user_request = st.text_area(
        "欲しい情報",
        "最新のGemini APIで使える主要モデルと特徴を知りたい",
        height=100,
    )
    max_results = st.slider("検索候補URL数", min_value=1, max_value=8, value=5)
    if st.button("Crawl4AI性能チェックを実行", type="primary"):
        with st.spinner("検索クエリ生成、URL探索、crawl4ai LLM抽出を実行中..."):
            result = run_crawl4ai_performance_check(user_request, max_results=max_results)
        if not result.success:
            log_error("Crawl4AI performance check", RuntimeError(result.error or "unknown error"))
            st.error("Crawl4AI性能チェックに失敗しました。")
            st.code(result.error or "unknown error")
            if result.timings:
                st.json(result.timings)
            return

        st.success("Crawl4AI性能チェックが完了しました。")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total sec", f"{result.timings.get('total_sec', 0):.2f}")
        col_b.metric("Markdown chars", result.markdown_chars)
        col_c.metric("HTML chars", result.cleaned_html_chars)

        st.write("Generated search query")
        st.code(result.search_query)
        st.write("Selected URL")
        st.code(result.selected_url)

        with st.expander("Candidate URLs"):
            st.json(result.candidate_urls)
        with st.expander("Attempted URLs"):
            st.json(result.attempted_urls)
        with st.expander("Timing details", expanded=True):
            st.json({key: round(value, 3) for key, value in result.timings.items()})
        st.write("Extracted content")
        st.code(result.extracted_content, language="json")


def render_adaptive_crawl() -> None:
    # crawl4ai AdaptiveCrawlerで、サイト内リンクを辿りながら調査範囲を広げます。
    from app.adaptive_crawler import adaptive_architecture_preview, run_adaptive_site_research

    st.subheader("Adaptive site research")
    st.caption("crawl4ai Adaptive Crawlingで、調査クエリに対してサイト内URLを辿り、十分な情報量に達するまで探索します。")

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
            st.error("Adaptive Crawlに失敗しました。設定、ネットワーク、Ollama/Geminiの状態を確認してください。")
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


def render_dataframe_mode() -> None:
    # PostgreSQLに保存したJSON生成結果をpandas DataFrameとして表示するページです。
    from app.view_db_dataframe import recipes_dataframe

    st.subheader("PostgreSQL contents")
    try:
        df = recipes_dataframe()
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as exc:
        log_error("DB DataFrame view", exc)
        st.error(f"DBを読み込めませんでした: {exc}")


def main() -> None:
    # Streamlitアプリ全体の入口です。sidebarで選んだmodeに応じて表示ページを切り替えます。
    apply_styles()
    force_rebuild, mode = render_sidebar()
    ensure_chat_history()
    ensure_qwen_chat_history()
    ensure_qwen_only_chat_history()
    ensure_gemini_chat_history()
    st.title("Recipe Inference RAG Chatbot")

    # サイドバーのradioで選ばれたモードごとに、描画関数を切り替えます。
    if mode == "Qwen RAG Chat":
        render_qwen_rag_chat(force_rebuild)
    elif mode == "Gemini RAG Chat":
        render_chat(force_rebuild, llm_backend="gemini")
    elif mode == "Qwen Chat":
        render_qwen_chat()
    elif mode == "Gemini Chat":
        render_gemini_chat()
    elif mode == "Crawl4AI Check":
        render_crawl4ai_check()
    elif mode == "Adaptive Crawl":
        render_adaptive_crawl()
    elif mode == "JSON + PostgreSQL":
        render_json_mode(force_rebuild)
    else:
        render_dataframe_mode()


try:
    main()
except Exception as exc:
    # 最後の安全網です。個別のtry/exceptで拾えなかったUIエラーをログに残します。
    log_error("Unhandled Streamlit UI error", exc)
    st.error("予期しないエラーが発生しました。開発者向けログに記録しました。")
    with st.expander("エラー詳細"):
        st.code(str(exc))
