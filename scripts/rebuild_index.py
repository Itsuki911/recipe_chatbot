from app.rag_chatbot import build_or_load_vector_store

if __name__ == "__main__":
    build_or_load_vector_store(force_rebuild=True)
    print("FAISS index rebuilt from Just One Cookbook pages.")
