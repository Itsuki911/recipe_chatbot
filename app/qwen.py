from __future__ import annotations

import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app import config
from app.rag_chatbot import RAGResponse, build_or_load_vector_store, format_docs


DEFAULT_QWEN_SYSTEM_PROMPT = (
    "You are a helpful chatbot. Answer directly and clearly. "
    "Do not claim that you used retrieved documents, because this test bot does not use RAG. "
    "Do not include hidden reasoning, chain-of-thought, or <think> blocks."
)


def build_qwen_llm():
    # OllamaはOpenAI互換APIを提供するため、LangChainのChatOpenAIから呼び出せます。
    # api_keyはOllama側では無視されますが、ChatOpenAIの必須引数としてダミー値を渡します。
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("Install langchain-openai to use Ollama Qwen RAG Chat.") from exc

    qwen_model = getattr(config, "QWEN_MODEL", "qwen3:4b")
    qwen_base_url = getattr(config, "QWEN_BASE_URL", "http://localhost:11434/v1")
    qwen_api_key = getattr(config, "QWEN_API_KEY", "ollama")
    return ChatOpenAI(
        model=qwen_model,
        base_url=qwen_base_url,
        api_key=qwen_api_key,
        temperature=0.1,
    )


def _strip_qwen_thinking(text: str) -> str:
    # Qwen3は環境によって <think>...</think> を返すことがあるため、UIには最終回答だけを出します。
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def ask_qwen(question: str, system_prompt: str = DEFAULT_QWEN_SYSTEM_PROMPT) -> str:
    # Qwen単体テスト用です。retriever、TurboVec、DB、mem0は使いません。
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = build_qwen_llm()
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question),
        ]
    )
    return _strip_qwen_thinking(str(response.content))


class QwenRAGChatbot:
    def __init__(self, force_rebuild_index: bool = False) -> None:
        # Gemini版と同じRAGシステム: TurboVec indexを読み込み、関連チャンク上位4件を検索します。
        self.vector_store = build_or_load_vector_store(force_rebuild=force_rebuild_index)
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 4})
        self.llm = build_qwen_llm()

        from app.memory import RecipeLongTermMemory

        self.memory = RecipeLongTermMemory()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a recipe inference assistant specializing in Japanese home cooking.
Use only the retrieved Just One Cookbook context below. If the context is insufficient,
say that the recipe database does not contain enough information.

Rules:
- Do not mix up recipes with similar names.
- Include ingredients, clear steps, and practical cooking notes.
- Explain relevant differences from similar Japanese dishes when useful.
- Mention source URLs briefly at the end.
- Answer in the same language as the user's question unless they ask otherwise.
- Use the user's long-term memory only for preferences, dietary constraints, and continuity.
- Do not include hidden reasoning, chain-of-thought, or <think> blocks in the answer.

Long-term user memory:
{memory}

Context:
{context}""",
                ),
                ("human", "{question}"),
            ]
        )
        self.chain = (prompt | self.llm | StrOutputParser()).with_retry(
            stop_after_attempt=3,
            wait_exponential_jitter=True,
        )

    def answer(self, question: str, user_id: str | None = None) -> RAGResponse:
        docs = self.retriever.invoke(question)
        memory = self.memory.search(question, user_id=user_id)
        answer = self.chain.invoke(
            {
                "context": format_docs(docs),
                "memory": memory or "No relevant user memory found.",
                "question": question,
            }
        )
        answer = _strip_qwen_thinking(answer)
        self.memory.add_interaction(question, answer, user_id=user_id)
        sources = sorted({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})
        return RAGResponse(answer=answer, sources=sources)
