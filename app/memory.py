from __future__ import annotations

from functools import cached_property
from typing import Any

from app import config


class RecipeLongTermMemory:
    """Small mem0 wrapper used by the LangChain RAG prompt."""

    def __init__(self, enabled: bool | None = None) -> None:
        # テストなどで明示的にenabledを渡せます。通常は .env / config の値を使います。
        self.enabled = config.MEM0_ENABLED if enabled is None else enabled

    @cached_property
    def client(self):
        # cached_propertyにより、mem0クライアントは初回アクセス時だけ作られます。
        # 起動時に重い初期化をしないための遅延初期化です。
        if not self.enabled:
            return None
        if not config.OPENROUTER_API_KEY:
            # mem0の要約や抽出にもOpenRouter free modelを使います。API keyが無い場合は無効扱いにします。
            return None

        from mem0 import Memory
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        from app.openrouter import get_active_openrouter_model, validate_free_openrouter_model

        # qdrantや履歴DBの保存先を先に作っておくと、初回実行時のFileNotFoundを防げます。
        config.MEM0_DIR.mkdir(parents=True, exist_ok=True)
        config.MEM0_QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        config.MEM0_HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        embeddings = FastEmbedEmbeddings(
            model_name=config.FASTEMBED_MODEL,
            cache_dir=str(config.FASTEMBED_CACHE_DIR),
        )
        active_model = get_active_openrouter_model()
        validate_free_openrouter_model(active_model)
        # mem0はLLM・embedding・vector storeをまとめて設定します。
        # このアプリでは会話の好みをローカルQdrantに保存します。
        memory_config: dict[str, Any] = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": active_model,
                    "api_key": config.OPENROUTER_API_KEY,
                    "openrouter_base_url": config.OPENROUTER_BASE_URL,
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
            # 質問に関連する過去の好みや制約だけをプロンプトに渡します。
            results = memory.search(
                query=query,
                filters={"user_id": user_id or config.MEM0_USER_ID},
                top_k=top_k,
            )
        except Exception:
            # メモリ検索に失敗しても、RAG本体の回答は続けられるようにします。
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
        # mem0は会話形式のmessagesから、今後役立つ好みや制約を抽出します。
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
            # 保存失敗でUIを止めないため、メモリ機能の例外は握りつぶします。
            return
