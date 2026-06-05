from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

try:
    from app.config import (
        DEEP_AGENT_LLM_BACKEND,
        LOCAL_RECIPE_DIR,
        OPENROUTER_MODEL,
        VECTOR_INDEX_DIR,
        WEB_RECIPE_REFERENCE_DIR,
    )
except ImportError:
    # config.pyのimport前に壊れても、Streamlit画面とログ出力を最低限続けるためのfallbackです。
    fallback_data_dir = Path(__file__).resolve().parent / "data"
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
    DEEP_AGENT_LLM_BACKEND = os.getenv("DEEP_AGENT_LLM_BACKEND", os.getenv("MAIN_LLM_BACKEND", "openrouter")).lower()
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
        or "402" in message
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
                "OpenRouter RAG Chat",
                "OpenRouter Chat",
                "past conversation",
                "Crawl4AI Check",
                "Adaptive Crawl",
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


def ensure_openrouter_chat_history() -> None:
    # OpenRouter単体テスト用の履歴です。RAGチャットの履歴とは分けます。
    if "openrouter_messages" not in st.session_state:
        st.session_state.openrouter_messages = [
            {
                "role": "assistant",
                "content": "こんにちは。RAGを使わず、OpenRouter free modelだけで回答します。",
            }
        ]


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
        " ".join(f'<span class="source-chip">{url}</span>' for url in sources),
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
    st.session_state.openrouter_pending_task = task
    render_openrouter_model_switch(task)
    return True


def deep_agent_offer_message(question: str) -> str:
    return (
        "ローカルのベクトルDBには、この質問へ直接答えるのに十分な情報が見つかりませんでした。\n\n"
        "Deep Agentで対象レシピの情報をWebから探して保存し、RAGインデックスを更新してから回答しますか？\n\n"
        f"対象: {question}\n\n"
        "Yes / No で答えてください。YesならDeep Agentを実行し、NoならLLM自身の一般知識で回答します。"
    )


def run_chat_deep_agent_answer(
    *,
    question: str,
    force_rebuild: bool,
    load_current_chatbot,
):
    from app.deep_agent import run_deep_agent_recipe_collection_with_details

    result = run_deep_agent_recipe_collection_with_details(question, max_pages=3)
    load_chatbot.clear()
    chatbot = load_current_chatbot(force_rebuild)
    response = chatbot.answer(question)
    return result, response


def ensure_rag_chatbot_capabilities(chatbot, reload_chatbot):
    required_methods = ("retrieve", "has_sufficient_context", "answer_from_docs", "answer_from_model_knowledge")
    if all(hasattr(chatbot, method_name) for method_name in required_methods):
        return chatbot
    load_chatbot.clear()
    return reload_chatbot()


def persist_current_conversation(*, ai_type: str, messages_key: str, conversation_key: str) -> None:
    from app.database import save_chat_conversation

    try:
        conversation_id = save_chat_conversation(
            ai_type=ai_type,
            messages=st.session_state.get(messages_key, []),
            conversation_id=st.session_state.get(conversation_key),
        )
        st.session_state[conversation_key] = conversation_id
    except Exception as exc:
        log_error("Chat conversation PostgreSQL save", exc, details=f"ai_type={ai_type}")
        st.session_state.conversation_save_error = str(exc)


def render_past_conversation() -> None:
    from app.database import fetch_chat_conversation, fetch_chat_conversations

    st.subheader("past conversation")
    selected_id = st.session_state.get("selected_conversation_id")

    if selected_id:
        conversation = fetch_chat_conversation(int(selected_id))
        if not conversation:
            st.warning("選択した会話が見つかりませんでした。")
            if st.button("一覧に戻る"):
                st.session_state.selected_conversation_id = None
                st.rerun()
            return

        if st.button("一覧に戻る"):
            st.session_state.selected_conversation_id = None
            st.rerun()

        created_at = conversation["created_at"].strftime("%Y-%m-%d %H:%M") if conversation.get("created_at") else "-"
        col_date, col_label, col_ai = st.columns(3)
        col_date.metric("Date", created_at)
        col_label.metric("Conversation", f"conversation{conversation['id']}")
        col_ai.metric("AI", conversation["ai_type"])
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
        st.error("過去会話をDBから読み込めませんでした。")
        with st.expander("エラー詳細"):
            st.code(str(exc))
        return

    if not conversations:
        st.info("保存済みの会話はまだありません。")
        return

    for conversation in conversations:
        created_at = conversation["created_at"].strftime("%Y-%m-%d %H:%M") if conversation.get("created_at") else "-"
        with st.container():
            col_date, col_label, col_ai = st.columns(3)
            col_date.markdown(f"**Date**  \n{created_at}")
            col_label.markdown(f"**Conversation**  \nconversation{conversation['id']}")
            col_ai.markdown(f"**AI**  \n{conversation['ai_type']}")
            if st.button("この会話を見る", key=f"view_conversation_{conversation['id']}", use_container_width=True):
                st.session_state.selected_conversation_id = conversation["id"]
                st.rerun()
            st.divider()



def render_openrouter_rag_chat(force_rebuild: bool) -> None:
    st.subheader("OpenRouter RAG Chat")
    st.caption(f"Active free model: `{active_openrouter_model_label()}`")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_task = st.session_state.get("openrouter_pending_task")
    if pending_task and pending_task.get("type") in {"openrouter_rag", "openrouter_rag_deep_agent_choice"}:
        if pending_task.get("needs_model_switch"):
            render_openrouter_model_switch(pending_task)
        question = pending_task["question"]
        task_type = pending_task["type"]
        choice = pending_task.get("choice")
        st.session_state.openrouter_pending_task = None
    else:
        question = None
        task_type = "openrouter_rag"
        choice = None

    pending = st.session_state.get("openrouter_rag_deep_agent_pending")
    if question is None and (user_text := st.chat_input("例: 豚汁の材料と作り方、普通の味噌汁との違いを教えて")):
        if pending:
            st.session_state.messages.append({"role": "user", "content": user_text})
            persist_current_conversation(
                ai_type="OpenRouter_RAG",
                messages_key="messages",
                conversation_key="openrouter_rag_conversation_id",
            )
            with st.chat_message("user"):
                st.markdown(user_text)
            parsed_choice = parse_yes_no(user_text)
            if parsed_choice is None:
                message = "Yes / No で答えてください。YesならDeep Agentで探し、NoならLLM自身の一般知識で回答します。"
                with st.chat_message("assistant"):
                    st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})
                persist_current_conversation(
                    ai_type="OpenRouter_RAG",
                    messages_key="messages",
                    conversation_key="openrouter_rag_conversation_id",
                )
                st.stop()
            question = pending["question"]
            choice = parsed_choice
            task_type = "openrouter_rag_deep_agent_choice"
            st.session_state.openrouter_rag_deep_agent_pending = None
        else:
            question = user_text
            st.session_state.messages.append({"role": "user", "content": question})
            persist_current_conversation(
                ai_type="OpenRouter_RAG",
                messages_key="messages",
                conversation_key="openrouter_rag_conversation_id",
            )
            with st.chat_message("user"):
                st.markdown(question)

    if question is None:
        return

    if task_type == "openrouter_rag_deep_agent_choice":
        with st.chat_message("assistant"):
            try:
                if choice:
                    with st.spinner("Deep Agentで情報を探して保存し、RAGインデックスを再作成しています..."):
                        result, response = run_chat_deep_agent_answer(
                            question=question,
                            force_rebuild=True,
                            load_current_chatbot=lambda rebuild: load_chatbot(rebuild, "openrouter"),
                        )
                    prefix = f"Deep Agentで{len(result.saved_pages)}件の参照を保存しました。\n\n"
                else:
                    chatbot = ensure_rag_chatbot_capabilities(
                        load_chatbot(False, "openrouter"),
                        lambda: load_chatbot(False, "openrouter"),
                    )
                    with st.spinner("OpenRouter free model自身の一般知識で回答を作成中..."):
                        response = chatbot.answer_from_model_knowledge(question)
                    prefix = "ローカルRAGではなく、OpenRouter free model自身の一般知識で回答します。\n\n"
            except Exception as exc:
                defer_for_openrouter_model_switch(
                    exc,
                    {
                        "type": "openrouter_rag_deep_agent_choice",
                        "question": question,
                        "choice": choice,
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
            st.markdown(prefix + response.answer)
            render_sources(response.sources)
        st.session_state.rebuild_index_next = False
        st.session_state.messages.append({"role": "assistant", "content": prefix + response.answer})
        persist_current_conversation(
            ai_type="OpenRouter_RAG",
            messages_key="messages",
            conversation_key="openrouter_rag_conversation_id",
        )
        st.stop()

    should_rebuild = force_rebuild or st.session_state.get("rebuild_index_next", False)
    if not recipe_knowledge_ready(should_rebuild):
        show_missing_recipe_data_message()
        st.stop()
    try:
        chatbot = load_chatbot(should_rebuild, "openrouter")
        chatbot = ensure_rag_chatbot_capabilities(
            chatbot,
            lambda: load_chatbot(should_rebuild, "openrouter"),
        )
        st.session_state.rebuild_index_next = False
    except RuntimeError as exc:
        show_recipe_source_error(exc)
        st.stop()

    with st.chat_message("assistant"):
        try:
            with st.spinner("レシピページを検索して、RAGで十分に答えられるか判定中..."):
                docs = chatbot.retrieve(question)
                has_context = chatbot.has_sufficient_context(question, docs)
            if not has_context:
                message = deep_agent_offer_message(question)
                st.markdown(message)
                st.session_state.openrouter_rag_deep_agent_pending = {"question": question}
                st.session_state.messages.append({"role": "assistant", "content": message})
                persist_current_conversation(
                    ai_type="OpenRouter_RAG",
                    messages_key="messages",
                    conversation_key="openrouter_rag_conversation_id",
                )
                st.stop()
            with st.spinner("RAG文脈を使ってOpenRouter free modelで回答を作成中..."):
                response = chatbot.answer_from_docs(question, docs)
        except Exception as exc:
            defer_for_openrouter_model_switch(
                exc,
                {
                    "type": "openrouter_rag",
                    "question": question,
                },
            )
            log_error("OpenRouter RAG chat response generation", exc, details=f"question={question}")
            error_message = "OpenRouter RAG回答生成中にエラーが発生しました。"
            show_generation_error(exc, error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            persist_current_conversation(
                ai_type="OpenRouter_RAG",
                messages_key="messages",
                conversation_key="openrouter_rag_conversation_id",
            )
            st.stop()
        st.markdown(response.answer)
        render_sources(response.sources)
    st.session_state.messages.append({"role": "assistant", "content": response.answer})
    persist_current_conversation(
        ai_type="OpenRouter_RAG",
        messages_key="messages",
        conversation_key="openrouter_rag_conversation_id",
    )


def render_openrouter_chat() -> None:
    from app.openrouter_chatbot import ask_openrouter

    st.subheader("OpenRouter Chat")
    st.caption(f"RAGなし。Active free model: `{active_openrouter_model_label()}`")

    for message in st.session_state.openrouter_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_task = st.session_state.get("openrouter_pending_task")
    if pending_task and pending_task.get("type") == "openrouter_chat":
        if pending_task.get("needs_model_switch"):
            render_openrouter_model_switch(pending_task)
        question = pending_task["question"]
        st.session_state.openrouter_pending_task = None
    elif question := st.chat_input("例: だし巻き卵の作り方を説明して"):
        st.session_state.openrouter_messages.append({"role": "user", "content": question})
        persist_current_conversation(
            ai_type="OpenRouter",
            messages_key="openrouter_messages",
            conversation_key="openrouter_conversation_id",
        )
        with st.chat_message("user"):
            st.markdown(question)
    else:
        return

    with st.chat_message("assistant"):
        try:
            with st.spinner("OpenRouter free modelに問い合わせ中..."):
                answer = ask_openrouter(question)
        except Exception as exc:
            defer_for_openrouter_model_switch(
                exc,
                {
                    "type": "openrouter_chat",
                    "question": question,
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
        st.markdown(answer)
    st.session_state.openrouter_messages.append({"role": "assistant", "content": answer})
    persist_current_conversation(
        ai_type="OpenRouter",
        messages_key="openrouter_messages",
        conversation_key="openrouter_conversation_id",
    )


def render_crawl4ai_check() -> None:
    # crawl4aiの検索クエリ生成、URL発見、LLM抽出、処理時間を確認するページです。
    from app.crawl4ai_performance import run_crawl4ai_performance_check

    st.subheader("Crawl4AI performance check")
    st.caption("URLを直接指定せず、ユーザー要望から検索クエリを作成して、候補URLを選び、crawl4aiでLLM抽出します。")
    user_request = st.text_area(
        "欲しい情報",
        "OpenRouterのfree model一覧と使い分けを知りたい",
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
    st.title("Recipe Inference RAG Chatbot")

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
