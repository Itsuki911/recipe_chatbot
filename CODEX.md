# CODEX Notes

## 2026-05-29

- Source notebook: `/Users/adachiitsuki/Downloads/gemma4-recipe-inference.ipynb`.
- Original notebook used Gemma, LangChain RAG, Just One Cookbook, structured JSON, and SQLite.
- This project version separates responsibilities into Python modules and changes persistence to PostgreSQL.
- RAG source is configured with `JOC_START_URL=https://www.justonecookbook.com/`.
- Local vector search uses FAISS under `data/faiss_index/`.
- PostgreSQL uses `DATABASE_URL`; see `.env.example`.
- If Gemma local loading is too heavy on this Mac, set `OPENAI_API_KEY` to use `langchain-openai` instead.
- Figma note: no target Figma file URL was provided, so `scripts/figma_ui_spec.md` stores the UI spec/tokens for efficient Figma reconstruction or capture after the app is running.
- Figma plugin attempt: `generate_figma_design` was invoked after the local Streamlit server started, but the connector responded that this environment should use `use_figma` instead. A target Figma file key/URL is needed for `use_figma`, so no canvas write was performed.
- Verification: `python -m compileall app app.py scripts`, module import check, and Playwright navigation to `http://localhost:8501` passed.
- Just One Cookbook may return 403 to Python `requests`. Added `data/joc_pages/` local fallback; saved `.html`, `.txt`, or `.md` files there are indexed before live web requests.
