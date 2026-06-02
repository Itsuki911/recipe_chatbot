from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ERROR_LOG_PATH = BASE_DIR / "ERROR_LOG.md"
TURBOVEC_INDEX_DIR = DATA_DIR / "turbovec_index"
VECTOR_INDEX_DIR = TURBOVEC_INDEX_DIR
LOCAL_RECIPE_DIR = DATA_DIR / "joc_pages"
MEM0_DIR = DATA_DIR / "mem0"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://recipe_user:recipe_password@localhost:5432/recipe_chatbot",
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

HF_MODEL_ID = os.getenv("HF_MODEL_ID", "google/gemma-4-E2B-it")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
FASTEMBED_MODEL = os.getenv("FASTEMBED_MODEL", EMBEDDING_MODEL)
FASTEMBED_CACHE_DIR = Path(os.getenv("FASTEMBED_CACHE_DIR", str(DATA_DIR / "fastembed_cache")))
EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "384"))
RAG_LLM_BACKEND = os.getenv("RAG_LLM_BACKEND", "gemini").lower()
RAG_EMBEDDING_BACKEND = os.getenv("RAG_EMBEDDING_BACKEND", "fastembed").lower()
RAG_VECTOR_STORE = os.getenv("RAG_VECTOR_STORE", "turbovec").lower()
TURBOVEC_BIT_WIDTH = int(os.getenv("TURBOVEC_BIT_WIDTH", "4"))

MEM0_ENABLED = os.getenv("MEM0_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
MEM0_USER_ID = os.getenv("MEM0_USER_ID", "recipe_chatbot_user")
MEM0_HISTORY_DB_PATH = Path(os.getenv("MEM0_HISTORY_DB_PATH", str(MEM0_DIR / "history.db")))
MEM0_QDRANT_PATH = Path(os.getenv("MEM0_QDRANT_PATH", str(MEM0_DIR / "qdrant")))

JOC_START_URL = os.getenv("JOC_START_URL", "https://www.justonecookbook.com/")
JOC_MAX_PAGES = int(os.getenv("JOC_MAX_PAGES", "12"))
JOC_RECIPE_URLS = [
    url.strip()
    for url in os.getenv(
        "JOC_RECIPE_URLS",
        ",".join(
            [
                "https://www.justonecookbook.com/tamagoyaki-japanese-rolled-omelette/",
                "https://www.justonecookbook.com/tonjiru/",
                "https://www.justonecookbook.com/miso-soup/",
                "https://www.justonecookbook.com/dashi/",
            ]
        ),
    ).split(",")
    if url.strip()
]
