# Recipe Inference RAG Chatbot

LangChainベースの和食レシピ推論特化RAG chatbotです。Just One CookbookをRAGの情報源にし、ChatGPT/Gemini風のStreamlit UI、JSON構造化出力、PostgreSQL保存、DataFrame閲覧を分離して実装しています。

## Features

- Just One Cookbook (`https://www.justonecookbook.com/`) からレシピページを取得
- LangChain + FAISS + HuggingFace embeddings によるRAG
- OpenAI APIがある場合はOpenAI、なければローカルHugging Faceモデルを使用
- レシピ提案をJSONとして生成
- JSON出力をPostgreSQLのJSONBカラムに保存
- VS Codeターミナル上でDataFrame形式のDB確認
- StreamlitのチャットUI
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

## Run

```bash
streamlit run app.py
```

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
CODEX.md                       # Development notes and error memo
```

## Notes

ローカルGemmaモデルは環境によって重い場合があります。その場合は `.env` に `OPENAI_API_KEY` を設定すると、OpenAIモデルで同じRAGパイプラインを使えます。
