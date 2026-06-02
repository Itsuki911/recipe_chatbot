from __future__ import annotations

from functools import cached_property
from typing import Any

from app import config


class RecipeLongTermMemory:
    """Small mem0 wrapper used by the LangChain RAG prompt."""

    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = config.MEM0_ENABLED if enabled is None else enabled

    @cached_property
    def client(self):
        if not self.enabled:
            return None
        if not config.GOOGLE_API_KEY:
            return None

        from mem0 import Memory
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

        config.MEM0_DIR.mkdir(parents=True, exist_ok=True)
        config.MEM0_QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        config.MEM0_HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        embeddings = FastEmbedEmbeddings(
            model_name=config.FASTEMBED_MODEL,
            cache_dir=str(config.FASTEMBED_CACHE_DIR),
        )
        memory_config: dict[str, Any] = {
            "llm": {
                "provider": "gemini",
                "config": {
                    "model": config.GEMINI_MODEL,
                    "api_key": config.GOOGLE_API_KEY,
                    "temperature": 0.1,
                    "max_tokens": 1200,
                },
            },
            "embedder": {
                "provider": "langchain",
                "config": {
                    "model": embeddings,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "recipe_chatbot_memory",
                    "path": str(config.MEM0_QDRANT_PATH),
                    "embedding_model_dims": config.EMBEDDING_DIMS,
                    "on_disk": True,
                },
            },
            "history_db_path": str(config.MEM0_HISTORY_DB_PATH),
        }
        return Memory.from_config(memory_config)

    def search(self, query: str, user_id: str | None = None, top_k: int = 5) -> str:
        memory = self.client
        if memory is None:
            return ""
        try:
            results = memory.search(
                query=query,
                filters={"user_id": user_id or config.MEM0_USER_ID},
                top_k=top_k,
            )
        except Exception:
            return ""

        items = results.get("results", results) if isinstance(results, dict) else results
        memories: list[str] = []
        for item in items or []:
            if isinstance(item, dict):
                text = item.get("memory") or item.get("text") or item.get("content")
            else:
                text = str(item)
            if text:
                memories.append(f"- {text}")
        return "\n".join(memories)

    def add_interaction(self, question: str, answer: str, user_id: str | None = None) -> None:
        memory = self.client
        if memory is None:
            return
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
        try:
            memory.add(
                messages,
                user_id=user_id or config.MEM0_USER_ID,
                metadata={"app": "recipe_chatbot"},
            )
        except Exception:
            return
