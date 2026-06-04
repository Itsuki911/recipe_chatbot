# CODEX Notes

## 2026-05-29

- Source notebook: `/Users/adachiitsuki/Downloads/gemma4-recipe-inference.ipynb`.
- Original notebook used Gemma, LangChain RAG, Just One Cookbook, structured JSON, and SQLite.
- This project version separates responsibilities into Python modules and changes persistence to PostgreSQL.
- RAG source is configured with `JOC_START_URL=https://www.justonecookbook.com/`.
- Local vector search now uses TurboVec under `data/turbovec_index/`.
- PostgreSQL uses `DATABASE_URL`; see `.env.example`.
- LLM backend now uses Gemini 2.5 Flash through `langchain-google-genai`; set `GOOGLE_API_KEY` in ignored `.env`.
- Figma note: no target Figma file URL was provided, so `scripts/figma_ui_spec.md` stores the UI spec/tokens for efficient Figma reconstruction or capture after the app is running.
- Figma plugin attempt: `generate_figma_design` was invoked after the local Streamlit server started, but the connector responded that this environment should use `use_figma` instead. A target Figma file key/URL is needed for `use_figma`, so no canvas write was performed.
- Verification: `python -m compileall app app.py scripts`, module import check, and Playwright navigation to `http://localhost:8501` passed.
- Just One Cookbook may return 403 to Python `requests`. Added `data/joc_pages/` local fallback; saved `.html`, `.txt`, or `.md` files there are indexed before live web requests.
- Added sidebar URL scraping and optional LangChain Deep Agents collection. Deep Agent requires `deepagents` plus `GOOGLE_API_KEY` and can be slow/resource-heavy.
- `deepagents` currently requires Python 3.11+, while the local environment is Python 3.10. Requirements use an environment marker so Python 3.10 installs still work; the app shows a runtime message for Deep Agent collection on Python 3.10.
- Developer error history is stored in `ERROR_LOG.md`. Runtime exceptions caught by Streamlit handlers are appended via `app/error_logger.py`.
- `app.py` now wraps the UI in `main()` with a top-level `try/except`, so unexpected RuntimeError/ImportError-style UI exceptions are logged to `ERROR_LOG.md`.
- After adding config fallback handling for `LOCAL_RECIPE_DIR`, the user confirmed the Streamlit app starts successfully.
- Chat answer generation errors are logged with context `Chat conversation response generation` and include the user question in the details.
- Chat/JSON now check for local recipe files or an existing TurboVec index before initializing RAG. Deep Agent collection is disabled in the UI unless Python 3.11+ and `GOOGLE_API_KEY` are available.
- Added and installed `accelerate` because local Hugging Face model loading uses `device_map="auto"`.
- Added Docker support (`Dockerfile`, `docker-compose.yml`, `.dockerignore`) to standardize package dependencies on Python 3.11 and include PostgreSQL. Host PostgreSQL is exposed on `localhost:5433` because `5432` can conflict with a local database.
- Local Hugging Face model loading now only uses `device_map="auto"` when `accelerate` is importable; otherwise it attempts a no-device-map load and raises a clearer RuntimeError if all model loads fail.
- Docker was applied and verified: `docker compose up -d` starts `app` on `http://localhost:8501` and PostgreSQL on host `localhost:5433`; app-to-db check returned `db ok`.
- Docker image `recipe_chatbot-app:latest` is about 9.8GB because the current dependency resolution pulls PyTorch plus NVIDIA/CUDA packages in the Linux image. Consider a Docker-specific lightweight dependency set later if disk/build time becomes a problem.
- Added `requirements-docker.txt` and changed Docker to Gemini + FastEmbed + TurboVec + mem0 mode. Docker Chat/JSON RAG requires `GOOGLE_API_KEY`; the container does not install `torch` or `transformers`.
- Verified Docker dependency resolution with `turbovec==0.6.0`, `mem0ai==2.0.4`, `fastembed==0.8.0`, and `langchain-google-genai==4.2.4`. App starts on `http://localhost:8501`, DB check returns `db ok`, and key-missing behavior reports `GOOGLE_API_KEY` clearly.
- FastEmbed model is `BAAI/bge-small-en-v1.5`; `intfloat/multilingual-e5-small` was not supported by FastEmbed 0.8.0, and the multilingual MiniLM model download was unstable in Docker.
- Completion audit: no Gemini API key string was found in tracked files; `.env` is ignored and untracked. Docker verified TurboVec retrieval (`retrieved: 4` from tamagoyaki local source), mem0 client init (`Memory`), DB (`db ok`), and Streamlit HTTP (`200 OK`). Full answer generation remains blocked until the leaked Gemini key is replaced.
- New Gemini API key was added to ignored `.env` and verified in Docker without printing the secret. Full RAG answer generation succeeded with Gemini 2.5 Flash, TurboVec, FastEmbed, and mem0. JSON generation and PostgreSQL save also succeeded with `database_id: 1`.
- mem0 long-term memory was directly verified in Docker by saving and searching a low-sugar tamagoyaki preference.
- Added `.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)` to both chat and JSON chains to handle temporary Gemini 503 high-demand errors.

## 2026-06-02

- Ollama local model storage check at `2026-06-02 21:14:23 JST`: `du -sh /Users/adachiitsuki/.ollama/models` reported `2.3G`.
- Mac filesystem capacity check: `/dev/disk3s5` mounted on `/System/Volumes/Data` reported `Size 228Gi`, `Used 186Gi`, `Avail 12Gi`, `Capacity 94%`.
- Note: Ollama models are stored under `/Users/adachiitsuki/.ollama/models`, not in the `recipe_chatbot` repository.
