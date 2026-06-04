# Recipe Inference RAG Chatbot

LangChainベースの和食レシピ推論特化RAG chatbotです。Just One CookbookをRAGの情報源にし、Qwen/Gemini対応のStreamlit UI、JSON構造化出力、PostgreSQL保存、DataFrame閲覧を分離して実装しています。

## Features

- Just One Cookbook (`https://www.justonecookbook.com/`) からレシピページを取得
- LangChain + TurboVec + FastEmbed によるRAG
- QwenをメインLLMとして使用し、Geminiにも切り替え可能
- mem0による会話のlong-term memory
- レシピ提案をJSONとして生成
- JSON出力をPostgreSQLのJSONBカラムに保存
- VS Codeターミナル上でDataFrame形式のDB確認
- StreamlitのチャットUI
- Streamlit sidebarからレシピURLを `data/joc_pages/` に保存
- crawl4ai Agentic CrawlerによるWeb上の関連レシピ参照の自動収集
- crawl4ai Adaptive Crawlingによるサイト内調査、内部リンク探索、LLM統合要約
- Figma用UI仕様: `scripts/figma_ui_spec.md`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

PostgreSQLを起動し、`.env` の `DATABASE_URL` を自分の環境に合わせてください。

```bash
python scripts/init_db.py
python scripts/rebuild_index.py
```

If Just One Cookbook returns `403 Forbidden` to Python requests, save recipe pages from your browser into `data/joc_pages/` as `.html`, `.txt`, or `.md`, then rebuild the index:

```bash
python scripts/rebuild_index.py
```

Local files in `data/joc_pages/` are loaded before live web requests.

The sidebar also includes:

- `ページをdataに保存`: input a recipe URL and save it into `data/joc_pages/`
- `Deep Agent自動収集`: ask a crawl4ai Agentic Crawler to search the web, choose seed URLs, deep-crawl relevant pages, and save references into `data/web_recipe_reference/`
- `Adaptive Crawl`: run crawl4ai Adaptive Crawling from a start URL and synthesize the site research with Qwen/Gemini

Deep Agent collection uses Qwen by default. If `DEEP_AGENT_LLM_BACKEND=gemini`, it also requires `GOOGLE_API_KEY`; it may take several minutes.
Both `data/joc_pages/` and `data/web_recipe_reference/` are loaded into the TurboVec RAG index when Chat/JSON triggers an index rebuild.

## Run

```bash
streamlit run app.py
```

## Docker

Dockerを使うとPython 3.11環境に固定できるため、`deepagents` などPythonバージョン依存のあるパッケージを扱いやすくなります。Docker実行は任意です。
Docker imageは `docker/requirements-docker.txt` を使い、Qwen、Gemini 2.5 Flash、FastEmbed、TurboVec、mem0を同じPython 3.11環境に固定します。DockerでQwenを使う場合はホスト側のOllamaが `http://localhost:11434` で動いている必要があります。Geminiへ切り替える場合は `.env` に `GOOGLE_API_KEY` が必要です。

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

App: `http://localhost:8501`
PostgreSQL from host tools: `localhost:5433`

The Docker Compose setup includes:

- `app`: Python 3.11 Streamlit app
- `db`: PostgreSQL 16
- Host-side PostgreSQL port is `5433` to avoid conflicts with local PostgreSQL on `5432`.
- Docker uses `MAIN_LLM_BACKEND=qwen`, `RAG_LLM_BACKEND=qwen`, `DEEP_AGENT_LLM_BACKEND=qwen`, `STRUCTURED_LLM_BACKEND=qwen`, `RAG_EMBEDDING_BACKEND=fastembed`, and `RAG_VECTOR_STORE=turbovec`.
- `../data:/app/data`: saved recipe pages, TurboVec index, FastEmbed cache, and mem0 persistence
- `../ERROR_LOG.md:/app/ERROR_LOG.md`: developer error log persistence

Gemini remains available by setting `RAG_LLM_BACKEND=gemini`, `DEEP_AGENT_LLM_BACKEND=gemini`, `STRUCTURED_LLM_BACKEND=gemini`, or `CRAWL4AI_LLM_PROVIDER=gemini/gemini-2.5-flash` and providing `GOOGLE_API_KEY` in `.env`.

## JSON output

```bash
python -m app.json_output "Please share a healthier high-protein version of dashi-maki tamago."
```

## View DB as DataFrame

```bash
python -m app.view_db_dataframe
```

## Project Structure

```text
app.py                         # Streamlit frontend
app/rag_chatbot.py             # LangChain RAG pipeline
app/adaptive_crawler.py        # crawl4ai Adaptive Crawling research pipeline
app/deep_agent.py              # crawl4ai Agentic Crawler web reference collection
app/json_output.py             # Structured JSON generation
app/database.py                # PostgreSQL schema and persistence
app/view_db_dataframe.py       # DB records as pandas DataFrame
docs/adaptive_crawling_architecture.md # Adaptive crawling architecture
scripts/init_db.py             # Create PostgreSQL tables
scripts/rebuild_index.py       # Crawl and index Just One Cookbook pages
scripts/figma_ui_spec.md       # Figma handoff spec
docker/Dockerfile              # Docker image definition
docker/docker-compose.yml      # Docker Compose services
docker/requirements-docker.txt # Docker-specific dependencies
```

## Notes

実キーは `.env` にのみ保存してください。`.env` は `.gitignore` 済みです。チャットに貼ったAPIキーは漏洩済みとして扱い、Google AI Studioで再発行することを推奨します。
