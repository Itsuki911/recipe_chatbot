from __future__ import annotations

import argparse

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import GEMINI_MODEL, GOOGLE_API_KEY


DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful chatbot. Answer directly and clearly. "
    "Do not claim that you used retrieved documents, because this test bot does not use RAG."
)


def build_gemini_llm():
    # This test chatbot uses Gemini only. It intentionally avoids RAG, DB, and long-term memory imports.
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add GOOGLE_API_KEY to .env before running the Gemini-only chatbot."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.2,
        google_api_key=GOOGLE_API_KEY,
    )


def ask_gemini(question: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> str:
    # Gemini receives only the system prompt and the user's question.
    # No retrieved recipe context is attached here, so this is useful for pure Gemini API testing.
    llm = build_gemini_llm()
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question),
        ]
    )
    return str(response.content).strip()


def main() -> None:
    # CLI usage:
    # python -m app.gemini_chatbot "だし巻き卵の作り方を教えて"
    parser = argparse.ArgumentParser(description="Ask Gemini directly without RAG, DB, or memory.")
    parser.add_argument("question", help="Question to send directly to Gemini")
    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM_PROMPT,
        help="Optional system prompt for Gemini-only testing",
    )
    args = parser.parse_args()
    print(ask_gemini(args.question, system_prompt=args.system))


if __name__ == "__main__":
    main()
