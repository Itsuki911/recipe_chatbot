import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag_chatbot import build_or_load_vector_store

if __name__ == "__main__":
    build_or_load_vector_store(force_rebuild=True)
    print("TurboVec index rebuilt from Just One Cookbook pages.")
