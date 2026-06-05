from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from app.config import DATABASE_URL

# SQLAlchemy Coreでは、MetaDataにテーブル定義を集めてから create_all でDBへ反映します。
metadata = MetaData()

# JSON生成したレシピ提案を保存するテーブルです。
# ingredients や steps はリスト構造を保ちたいので PostgreSQL の JSONB を使います。
proposed_recipes = Table(
    "proposed_recipes",
    metadata,
    # PostgreSQL maps Integer primary key to a generated identity/autoincrement column.
    # Keeping this Core table simple makes pandas reads and SQL inspection painless.
    Column("id", Integer, primary_key=True),
    Column("recipe_name", String(255), nullable=False),
    Column("question", Text, nullable=False),
    Column("health_focus_explanation", Text),
    Column("ingredients", JSONB, nullable=False),
    Column("steps", JSONB, nullable=False),
    Column("source_urls", JSONB, nullable=False),
    Column("raw_json", JSONB, nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

chat_conversations = Table(
    "chat_conversations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ai_type", String(32), nullable=False),
    Column("messages", JSONB, nullable=False),
    Column("raw_json", JSONB, nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

openrouter_model_usage = Table(
    "openrouter_model_usage",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("model_id", String(255), nullable=False),
    Column("prompt_tokens", Integer, nullable=False, default=0),
    Column("completion_tokens", Integer, nullable=False, default=0),
    Column("total_tokens", Integer, nullable=False, default=0),
    Column("request_status", String(32), nullable=False, default="success"),
    Column("raw_json", JSONB, nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)


def get_engine(database_url: str = DATABASE_URL) -> Engine:
    # pool_pre_ping=True にすると、切れたDB接続を使い回す前に確認してくれます。
    return create_engine(database_url, pool_pre_ping=True)


def init_db(engine: Engine | None = None) -> None:
    # テーブルが存在しない場合だけ作成します。既にある場合は何もしません。
    engine = engine or get_engine()
    metadata.create_all(engine)


def save_recipe_output(
    recipe: dict[str, Any],
    question: str,
    source_urls: list[str],
    engine: Engine | None = None,
) -> int:
    engine = engine or get_engine()
    init_db(engine)
    # LLMの出力には欠ける項目がある可能性があるため、保存前にデフォルト値を補います。
    payload = {
        "recipe_name": recipe.get("recipe_name") or "Untitled recipe",
        "question": question,
        "health_focus_explanation": recipe.get("health_focus_explanation", ""),
        "ingredients": recipe.get("ingredients", []),
        "steps": recipe.get("steps", []),
        "source_urls": source_urls,
        "raw_json": recipe,
        "created_at": datetime.utcnow(),
    }
    # engine.begin() は成功時commit、失敗時rollbackを自動で行います。
    with engine.begin() as conn:
        result = conn.execute(proposed_recipes.insert().returning(proposed_recipes.c.id), payload)
        return int(result.scalar_one())


def fetch_recipes(engine: Engine | None = None) -> list[dict[str, Any]]:
    engine = engine or get_engine()
    init_db(engine)
    with engine.connect() as conn:
        # 新しいレシピ提案ほど上に表示できるよう、created_atの降順で取得します。
        rows = conn.execute(select(proposed_recipes).order_by(proposed_recipes.c.created_at.desc()))
        return [dict(row._mapping) for row in rows]


def save_chat_conversation(
    *,
    ai_type: str,
    messages: list[dict[str, Any]],
    conversation_id: int | None = None,
    engine: Engine | None = None,
) -> int:
    engine = engine or get_engine()
    init_db(engine)
    now = datetime.utcnow()
    normalized_messages = [
        {
            "role": str(message.get("role", "")),
            "content": str(message.get("content", "")),
        }
        for message in messages
        if message.get("role") and message.get("content")
    ]
    raw_json = {
        "ai_type": ai_type,
        "messages": normalized_messages,
    }
    with engine.begin() as conn:
        if conversation_id is not None:
            conn.execute(
                chat_conversations.update()
                .where(chat_conversations.c.id == conversation_id)
                .values(
                    ai_type=ai_type,
                    messages=normalized_messages,
                    raw_json=raw_json,
                    updated_at=now,
                )
            )
            return conversation_id

        result = conn.execute(
            chat_conversations.insert().returning(chat_conversations.c.id),
            {
                "ai_type": ai_type,
                "messages": normalized_messages,
                "raw_json": raw_json,
                "created_at": now,
                "updated_at": now,
            },
        )
        return int(result.scalar_one())


def fetch_chat_conversations(engine: Engine | None = None) -> list[dict[str, Any]]:
    engine = engine or get_engine()
    init_db(engine)
    with engine.connect() as conn:
        rows = conn.execute(select(chat_conversations).order_by(chat_conversations.c.created_at.desc()))
        return [dict(row._mapping) for row in rows]


def fetch_chat_conversation(conversation_id: int, engine: Engine | None = None) -> dict[str, Any] | None:
    engine = engine or get_engine()
    init_db(engine)
    with engine.connect() as conn:
        row = conn.execute(
            select(chat_conversations).where(chat_conversations.c.id == conversation_id)
        ).mappings().first()
        return dict(row) if row else None


def record_openrouter_usage(
    *,
    model_id: str,
    usage: dict[str, Any] | None = None,
    request_status: str = "success",
    raw_json: dict[str, Any] | None = None,
    engine: Engine | None = None,
) -> None:
    engine = engine or get_engine()
    init_db(engine)
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
    with engine.begin() as conn:
        conn.execute(
            openrouter_model_usage.insert(),
            {
                "model_id": model_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "request_status": request_status,
                "raw_json": raw_json or {"usage": usage},
                "created_at": datetime.utcnow(),
            },
        )


def fetch_openrouter_usage_ranking(limit: int = 5, engine: Engine | None = None) -> list[dict[str, Any]]:
    from sqlalchemy import desc, func

    engine = engine or get_engine()
    init_db(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                openrouter_model_usage.c.model_id,
                func.count(openrouter_model_usage.c.id).label("requests"),
                func.coalesce(func.sum(openrouter_model_usage.c.total_tokens), 0).label("total_tokens"),
                func.max(openrouter_model_usage.c.created_at).label("last_used_at"),
            )
            .where(openrouter_model_usage.c.request_status == "success")
            .group_by(openrouter_model_usage.c.model_id)
            .order_by(desc("total_tokens"), desc("requests"))
            .limit(limit)
        )
        return [dict(row._mapping) for row in rows]
