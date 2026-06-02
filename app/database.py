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
