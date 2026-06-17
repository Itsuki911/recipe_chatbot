# Recipe Inference RAG Chatbot

LangChainベースの和食レシピ推論特化RAG chatbotです。Just One CookbookをRAGの情報源にし、OpenRouter free model対応のStreamlit UI、JSON構造化出力、PostgreSQL保存、DataFrame閲覧を分離して実装しています。

## Features

- Just One Cookbook (`https://www.justonecookbook.com/`) からレシピページを取得
- LangChain + TurboVec + FastEmbed によるRAG
- OpenRouter経由で `:free` モデルだけを使用
- 429 Too Many Requests時にOpenRouter free model候補を表示し、選択後に現在のタスクを継続
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
- `Adaptive Crawl`: run crawl4ai Adaptive Crawling from a start URL and synthesize the site research with OpenRouter free model

Deep Agent collection uses OpenRouter free model by default and requires `OPENROUTER_API_KEY`; it may take several minutes.
Both `data/joc_pages/` and `data/web_recipe_reference/` are loaded into the TurboVec RAG index when Chat/JSON triggers an index rebuild.

## Run

```bash
streamlit run app.py
```

## Docker

Dockerを使うとPython 3.11環境に固定できるため、`deepagents` などPythonバージョン依存のあるパッケージを扱いやすくなります。Docker実行は任意です。
Docker imageは `docker/requirements-docker.txt` を使い、OpenRouter、FastEmbed、TurboVec、mem0を同じPython 3.11環境に固定します。OpenRouterを使うには `.env` に `OPENROUTER_API_KEY` が必要です。

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
- Docker uses `MAIN_LLM_BACKEND=openrouter`, `RAG_LLM_BACKEND=openrouter`, `DEEP_AGENT_LLM_BACKEND=openrouter`, `STRUCTURED_LLM_BACKEND=openrouter`, `RAG_EMBEDDING_BACKEND=fastembed`, and `RAG_VECTOR_STORE=turbovec`.
- `../data:/app/data`: saved recipe pages, TurboVec index, FastEmbed cache, and mem0 persistence
- `../ERROR_LOG.md:/app/ERROR_LOG.md`: developer error log persistence

The default OpenRouter model is `google/gemma-4-26b-a4b-it:free`. Any model configured in `.env` must end with `:free`; otherwise the app raises an error before making a paid request.

## Cloud Run / Supabase migration

このリポジトリはCloud Run移行用に、次の構成へ対応しています。

```text
Cloud Run Service: Streamlit web app
Cloud Run Job: Deep Agent collection
Cloud Storage: collected recipe text/html and job status
Supabase Postgres: DATABASE_URL
Secret Manager: OPENROUTER_API_KEY and DATABASE_URL
Cloud Build: GitHub pushからbuild/deploy
```

ローカル開発では `GCS_BUCKET` を空にすると、従来どおり `data/` 配下を使います。Cloud Runでは `GCS_BUCKET` を設定すると、`joc_pages/` と `web_recipe_reference/` の保存内容をCloud Storageにもアップロードし、RAG読み込み時にもCloud Storage上の `.html`, `.txt`, `.md` を参照します。

### Required secrets

OpenRouterとSupabaseの値はGoogle Secret Managerに保存します。実キーやDB URLをGitHubへcommitしないでください。

```bash
printf '%s' 'OPENROUTER_API_KEY_VALUE' |
gcloud secrets create openrouter-api-key --data-file=- --project recipe-chatbot-499108

printf '%s' 'postgresql+psycopg2://postgres.PROJECT_REF:PASSWORD@aws-REGION.pooler.supabase.com:6543/postgres?sslmode=require' |
gcloud secrets create supabase-database-url --data-file=- --project recipe-chatbot-499108
```

既にSecretを作成済みの場合は `create` ではなく `versions add` を使います。

```bash
printf '%s' 'NEW_VALUE' |
gcloud secrets versions add openrouter-api-key --data-file=- --project recipe-chatbot-499108
```

SupabaseはCloud Runのような自動スケーリング環境では、基本的にTransaction Poolerの接続文字列を使います。Supabase Dashboardの `Connect` からTransaction modeを選び、SQLAlchemy用に先頭を `postgresql+psycopg2://` にします。

### Required Google Cloud resources

`cloudbuild.yaml` の `_GCS_BUCKET` は、あなたが作成したBucket名に置き換えてください。

```yaml
_GCS_BUCKET: REPLACE_WITH_YOUR_BUCKET_NAME
```

Artifact Registry repositoryが未作成の場合:

```bash
gcloud artifacts repositories create recipe-chatbot \
  --repository-format=docker \
  --location=asia-northeast1 \
  --project recipe-chatbot-499108
```

Service Accountが未作成の場合:

```bash
gcloud iam service-accounts create recipe-web-sa --project recipe-chatbot-499108
gcloud iam service-accounts create recipe-job-sa --project recipe-chatbot-499108
```

Bucket権限:

```bash
gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET_NAME \
  --member="serviceAccount:recipe-web-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/storage.objectUser"

gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET_NAME \
  --member="serviceAccount:recipe-job-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/storage.objectUser"
```

Secret参照権限:

```bash
gcloud secrets add-iam-policy-binding openrouter-api-key \
  --member="serviceAccount:recipe-web-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project recipe-chatbot-499108

gcloud secrets add-iam-policy-binding openrouter-api-key \
  --member="serviceAccount:recipe-job-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project recipe-chatbot-499108

gcloud secrets add-iam-policy-binding supabase-database-url \
  --member="serviceAccount:recipe-web-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project recipe-chatbot-499108

gcloud secrets add-iam-policy-binding supabase-database-url \
  --member="serviceAccount:recipe-job-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project recipe-chatbot-499108
```

Web ServiceがCloud Run Jobを起動するには、Web Service AccountにJob実行権限が必要です。

```bash
gcloud projects add-iam-policy-binding recipe-chatbot-499108 \
  --member="serviceAccount:recipe-web-sa@recipe-chatbot-499108.iam.gserviceaccount.com" \
  --role="roles/run.developer"
```

### Manual deploy

GitHub連携の前に手動で確認する場合:

```bash
gcloud builds submit \
  --tag asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot/app:manual \
  --project recipe-chatbot-499108

gcloud run deploy recipe-chatbot-web \
  --image asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot/app:manual \
  --region asia-northeast1 \
  --port 8501 \
  --service-account recipe-web-sa@recipe-chatbot-499108.iam.gserviceaccount.com \
  --set-env-vars GCS_BUCKET=YOUR_BUCKET_NAME,GCS_PREFIX=recipe-chatbot,CLOUD_RUN_PROJECT_ID=recipe-chatbot-499108,CLOUD_RUN_REGION=asia-northeast1,CLOUD_RUN_DEEP_AGENT_JOB=recipe-deep-agent,MEM0_ENABLED=false \
  --set-secrets OPENROUTER_API_KEY=openrouter-api-key:latest,DATABASE_URL=supabase-database-url:latest \
  --allow-unauthenticated \
  --project recipe-chatbot-499108

gcloud run jobs deploy recipe-deep-agent \
  --image asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot/app:manual \
  --region asia-northeast1 \
  --service-account recipe-job-sa@recipe-chatbot-499108.iam.gserviceaccount.com \
  --command python \
  --args=-m,app.deep_agent_job \
  --task-timeout 30m \
  --max-retries 1 \
  --memory 2Gi \
  --set-env-vars GCS_BUCKET=YOUR_BUCKET_NAME,GCS_PREFIX=recipe-chatbot \
  --set-secrets OPENROUTER_API_KEY=openrouter-api-key:latest,DATABASE_URL=supabase-database-url:latest \
  --project recipe-chatbot-499108
```

Job単体テスト:

```bash
gcloud run jobs execute recipe-deep-agent \
  --region asia-northeast1 \
  --update-env-vars DEEP_AGENT_QUERY="tonjiru recipe technique",DEEP_AGENT_MAX_PAGES=2 \
  --wait \
  --project recipe-chatbot-499108
```

### GitHub deploy

Cloud BuildでGitHub repository `Itsuki911/recipe_chatbot` を接続し、`main` branchへのpushをトリガーにして `cloudbuild.yaml` を実行します。初回前に `cloudbuild.yaml` の `_GCS_BUCKET` を実Bucket名へ変更してください。

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
app/openrouter.py              # OpenRouter free model gateway, usage logging, and 429 switch support
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
