# Recipe Inference RAG Chatbot

LangChainベースの和食レシピ推論特化RAG chatbotです。Just One CookbookをRAGの情報源にし、ChatGPT/Gemini風のStreamlit UI、JSON構造化出力、PostgreSQL保存、DataFrame閲覧を分離して実装しています。

## Features

- Just One Cookbook (`https://www.justonecookbook.com/`) からレシピページを取得
- LangChain + TurboVec + FastEmbed によるRAG
- Gemini 2.5 Flashを回答生成モデルとして使用
- mem0による会話のlong-term memory
- レシピ提案をJSONとして生成
- JSON出力をPostgreSQLのJSONBカラムに保存
- VS Codeターミナル上でDataFrame形式のDB確認
- StreamlitのチャットUI
- Streamlit sidebarからレシピURLを `data/joc_pages/` に保存
- LangChain Deep Agentsによる関連レシピページの自動収集
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
- `Deep Agent自動収集`: ask a Deep Agent to search and save related recipe pages

Deep Agent collection requires Python 3.11+, `deepagents`, and `GOOGLE_API_KEY`; it may take several minutes.

## Run

```bash
streamlit run app.py
```

## Docker

Dockerを使うとPython 3.11環境に固定できるため、`deepagents` などPythonバージョン依存のあるパッケージを扱いやすくなります。Docker実行は任意です。
Docker imageは `docker/requirements-docker.txt` を使い、Gemini 2.5 Flash、FastEmbed、TurboVec、mem0を同じPython 3.11環境に固定します。DockerでChat/JSON RAGを使う場合は `.env` に `GOOGLE_API_KEY` が必要です。

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
- Docker uses `RAG_LLM_BACKEND=gemini`, `RAG_EMBEDDING_BACKEND=fastembed`, and `RAG_VECTOR_STORE=turbovec`.
- `../data:/app/data`: saved recipe pages, TurboVec index, FastEmbed cache, and mem0 persistence
- `../ERROR_LOG.md:/app/ERROR_LOG.md`: developer error log persistence

Deep Agent collection also uses `GOOGLE_API_KEY` in `.env`.

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
app/json_output.py             # Structured JSON generation
app/database.py                # PostgreSQL schema and persistence
app/view_db_dataframe.py       # DB records as pandas DataFrame
scripts/init_db.py             # Create PostgreSQL tables
scripts/rebuild_index.py       # Crawl and index Just One Cookbook pages
scripts/figma_ui_spec.md       # Figma handoff spec
docker/Dockerfile              # Docker image definition
docker/docker-compose.yml      # Docker Compose services
docker/requirements-docker.txt # Docker-specific dependencies
```

## Notes

実キーは `.env` にのみ保存してください。`.env` は `.gitignore` 済みです。チャットに貼ったAPIキーは漏洩済みとして扱い、Google AI Studioで再発行することを推奨します。
