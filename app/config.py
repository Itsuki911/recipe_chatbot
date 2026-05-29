from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"
LOCAL_RECIPE_DIR = DATA_DIR / "joc_pages"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://recipe_user:recipe_password@localhost:5432/recipe_chatbot",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

HF_MODEL_ID = os.getenv("HF_MODEL_ID", "google/gemma-4-E2B-it")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")

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
