from __future__ import annotations

import json
from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.database import save_recipe_output
from app.rag_chatbot import RecipeRAGChatbot, format_docs


class RecipeProposal(BaseModel):
    recipe_name: str = Field(description="Recipe name")
    health_focus_explanation: str = Field(
        description="How the recipe is adapted to the user's health goals or preferences"
    )
    ingredients: list[str] = Field(description="Ingredient list")
    steps: list[str] = Field(description="Step-by-step cooking instructions")


DEFAULT_USER_PROFILE = {
    "health_status": "コレステロール値が少し高め",
    "preferences": ["和食が好き", "甘さ控えめを好む"],
    "focus": ["筋トレのための高タンパク", "ダイエットのための低糖質"],
}


def generate_recipe_json(
    question: str,
    user_profile: dict[str, Any] | None = None,
    save_to_db: bool = True,
    force_rebuild_index: bool = False,
) -> dict[str, Any]:
    chatbot = RecipeRAGChatbot(force_rebuild_index=force_rebuild_index)
    docs = chatbot.retriever.invoke(question)
    context = format_docs(docs)
    parser = PydanticOutputParser(pydantic_object=RecipeProposal)
    profile = user_profile or DEFAULT_USER_PROFILE
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Japanese recipe personalization assistant.
Use the retrieved Just One Cookbook context and the user profile to produce valid JSON only.
Do not invent details that conflict with the context.

User profile:
{profile}

Retrieved context:
{context}

{format_instructions}""",
            ),
            ("human", "{question}"),
        ]
    )
    chain = (prompt | chatbot.llm | parser).with_retry(
        stop_after_attempt=3,
        wait_exponential_jitter=True,
    )
    proposal = chain.invoke(
        {
            "question": question,
            "profile": json.dumps(profile, ensure_ascii=False, indent=2),
            "context": context,
            "format_instructions": parser.get_format_instructions(),
        }
    )
    result = proposal.model_dump()
    source_urls = sorted({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})
    result["source_urls"] = source_urls
    if save_to_db:
        result["database_id"] = save_recipe_output(result, question=question, source_urls=source_urls)
    return result


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(description="Generate structured recipe JSON and save it to PostgreSQL.")
    arg_parser.add_argument("question", help="Recipe request")
    arg_parser.add_argument("--no-save", action="store_true", help="Print JSON without saving to PostgreSQL")
    args = arg_parser.parse_args()
    print(json.dumps(generate_recipe_json(args.question, save_to_db=not args.no_save), ensure_ascii=False, indent=2))
