from __future__ import annotations

import streamlit as st

from app.json_output import generate_recipe_json
from app.rag_chatbot import RecipeRAGChatbot
from app.view_db_dataframe import recipes_dataframe

st.set_page_config(page_title="Recipe RAG Chatbot", page_icon="🍱", layout="wide")

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

with st.sidebar:
    st.title("Recipe RAG")
    st.caption("Just One Cookbookを検索して、和食レシピ推論に特化して回答します。")
    force_rebuild = st.button("RAGインデックスを再作成")
    mode = st.radio("モード", ["Chat", "JSON + PostgreSQL", "DB DataFrame"], label_visibility="collapsed")

@st.cache_resource(show_spinner="Loading recipe knowledge base...")
def load_chatbot(force_rebuild_index: bool = False) -> RecipeRAGChatbot:
    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index)


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "こんにちは。Just One Cookbookの情報を元に、和食レシピを一緒に組み立てます。",
        }
    ]

st.title("Recipe Inference RAG Chatbot")

if mode == "Chat":
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("例: 豚汁の材料と作り方、普通の味噌汁との違いを教えて"):
        chatbot = load_chatbot(force_rebuild)
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("レシピページを検索して回答を作成中..."):
                response = chatbot.answer(question)
            st.markdown(response.answer)
            if response.sources:
                st.caption("Sources")
                st.markdown(
                    " ".join(f'<span class="source-chip">{url}</span>' for url in response.sources),
                    unsafe_allow_html=True,
                )
        st.session_state.messages.append({"role": "assistant", "content": response.answer})

elif mode == "JSON + PostgreSQL":
    st.subheader("Structured recipe JSON")
    question = st.text_area(
        "レシピ要望",
        "Please share a healthier high-protein version of dashi-maki tamago.",
        height=100,
    )
    if st.button("JSONを生成してDBに保存", type="primary"):
        with st.spinner("RAG検索、JSON生成、PostgreSQL保存を実行中..."):
            result = generate_recipe_json(question, save_to_db=True)
        st.success(f"Saved to PostgreSQL. id={result.get('database_id')}")
        st.json(result)

else:
    st.subheader("PostgreSQL contents")
    try:
        df = recipes_dataframe()
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"DBを読み込めませんでした: {exc}")
