from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.llm import build_qwen_llm, strip_hidden_reasoning
from app.rag_chatbot import RAGResponse, build_or_load_vector_store, format_docs


DEFAULT_QWEN_SYSTEM_PROMPT = (
    "You are a helpful chatbot. Answer directly and clearly. "
    "Do not claim that you used retrieved documents, because this test bot does not use RAG. "
    "Do not include hidden reasoning, chain-of-thought, or <think> blocks."
)


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
    return strip_hidden_reasoning(str(response.content))


class QwenRAGChatbot:
    def __init__(self, force_rebuild_index: bool = False) -> None:
        # 共通RAGシステム: TurboVec indexを読み込み、関連チャンク上位4件を検索します。
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
Use only the retrieved recipe reference context below. If the context is insufficient,
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
        answer = strip_hidden_reasoning(answer)
        self.memory.add_interaction(question, answer, user_id=user_id)
        sources = sorted({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})
        return RAGResponse(answer=answer, sources=sources)
