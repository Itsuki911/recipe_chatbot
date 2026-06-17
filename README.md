# Recipe Inference RAG Chatbot

Japanese home-cooking recipe assistant built with Streamlit, LangChain, OpenRouter, Supabase Postgres, Google Cloud Run, and Cloud Storage.

The app answers recipe questions with retrieval augmented generation (RAG), stores structured recipe outputs, and can run a separate Deep Agent crawler job to collect additional recipe references.

## Live App

Public Cloud Run deployment:

```text
https://recipe-chatbot-web-bvyktzzbcq-an.a.run.app
```

## Features

- Streamlit chat UI for recipe Q&A
- RAG over saved recipe reference documents
- OpenRouter free-model gateway with safety checks for `:free` model IDs
- JSON structured recipe generation
- Supabase Postgres persistence through SQLAlchemy
- Cloud Run Service for the web app
- Cloud Run Job for long-running Deep Agent collection
- Cloud Storage for collected text/html references and job status files
- Cloud Build deployment from GitHub `main`
- Local Docker Compose development with PostgreSQL

## Architecture

```text
GitHub main
  -> Cloud Build
  -> Artifact Registry
  -> Cloud Run Service: recipe-chatbot-web
  -> Cloud Run Job: recipe-deep-agent

Cloud Run Service
  -> OpenRouter API
  -> Supabase Postgres
  -> Cloud Storage
  -> Cloud Run Job API

Cloud Run Job
  -> OpenRouter API
  -> Web crawling
  -> Cloud Storage
```

Cloud Run resource names for the current deployment:

```text
Project: recipe-chatbot-499108
Region: asia-northeast1
Service: recipe-chatbot-web
Job: recipe-deep-agent
Artifact Registry repo: recipe-chatbot
Cloud Storage bucket: recipe-robot
GCS prefix: recipe-chatbot
```

## User Workflow

1. Open the Cloud Run URL.
2. Use the chat or JSON output modes.
3. Save recipe pages from the sidebar when a direct source URL is known.
4. Use Deep Agent collection for broader web reference gathering.
5. Rebuild the RAG index when new reference pages are added.

Deep Agent collection can take several minutes. In Cloud Run, it is started as a Cloud Run Job instead of blocking the Streamlit process.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with local or cloud credentials.

Required for OpenRouter-backed generation:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it:free
```

For local PostgreSQL, use a local `DATABASE_URL`.

```env
DATABASE_URL=postgresql+psycopg2://recipe_user:recipe_password@localhost:5432/recipe_chatbot
```

Initialize tables and optionally rebuild the local RAG index:

```bash
python scripts/init_db.py
python scripts/rebuild_index.py
```

Run the app:

```bash
streamlit run app.py
```

## Docker Development

Docker Compose provides a Python 3.11 app container and PostgreSQL 16.

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

Local URLs:

```text
App: http://localhost:8501
PostgreSQL from host tools: localhost:5433
```

The Docker setup mounts local persistence:

- `data/` for saved references, TurboVec index, FastEmbed cache, and mem0 data
- `ERROR_LOG.md` for local error logging

## Cloud Configuration

Cloud Run reads runtime secrets from Secret Manager.

Required Secret Manager entries:

```text
openrouter-api-key
supabase-database-url
```

`supabase-database-url` must be a PostgreSQL connection string, not the Supabase HTTP API URL. For Cloud Run, use the Supabase Transaction Pooler on port `6543`.

```text
postgresql+psycopg2://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@aws-REGION.pooler.supabase.com:6543/postgres?sslmode=require
```

Runtime environment variables:

| Variable | Purpose |
| --- | --- |
| `GCS_BUCKET` | Cloud Storage bucket name, for example `recipe-robot` |
| `GCS_PREFIX` | Object prefix, currently `recipe-chatbot` |
| `CLOUD_RUN_PROJECT_ID` | Google Cloud project ID |
| `CLOUD_RUN_REGION` | Cloud Run region |
| `CLOUD_RUN_DEEP_AGENT_JOB` | Cloud Run Job name |
| `MEM0_ENABLED` | Usually `false` on Cloud Run unless external persistence is configured |

The production deploy uses:

```text
GCS_BUCKET=recipe-robot
GCS_PREFIX=recipe-chatbot
CLOUD_RUN_PROJECT_ID=recipe-chatbot-499108
CLOUD_RUN_REGION=asia-northeast1
CLOUD_RUN_DEEP_AGENT_JOB=recipe-deep-agent
MEM0_ENABLED=false
```

## Deployment

Deployment is defined in `cloudbuild.yaml`.

On push to GitHub `main`, Cloud Build:

1. Builds the Docker image.
2. Pushes it to Artifact Registry.
3. Deploys `recipe-chatbot-web` as a Cloud Run Service.
4. Deploys `recipe-deep-agent` as a Cloud Run Job.

Manual build/deploy is also possible:

```bash
gcloud builds submit \
  --tag asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot/app:manual \
  --project recipe-chatbot-499108
```

```bash
gcloud run deploy recipe-chatbot-web \
  --image asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot/app:manual \
  --region asia-northeast1 \
  --port 8501 \
  --service-account recipe-web-sa@recipe-chatbot-499108.iam.gserviceaccount.com \
  --set-env-vars GCS_BUCKET=recipe-robot,GCS_PREFIX=recipe-chatbot,CLOUD_RUN_PROJECT_ID=recipe-chatbot-499108,CLOUD_RUN_REGION=asia-northeast1,CLOUD_RUN_DEEP_AGENT_JOB=recipe-deep-agent,MEM0_ENABLED=false \
  --set-secrets OPENROUTER_API_KEY=openrouter-api-key:latest,DATABASE_URL=supabase-database-url:latest \
  --allow-unauthenticated \
  --project recipe-chatbot-499108
```

```bash
gcloud run jobs deploy recipe-deep-agent \
  --image asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot/app:manual \
  --region asia-northeast1 \
  --service-account recipe-job-sa@recipe-chatbot-499108.iam.gserviceaccount.com \
  --command python \
  --args=-m,app.deep_agent_job \
  --task-timeout 30m \
  --max-retries 1 \
  --memory 2Gi \
  --set-env-vars GCS_BUCKET=recipe-robot,GCS_PREFIX=recipe-chatbot \
  --set-secrets OPENROUTER_API_KEY=openrouter-api-key:latest,DATABASE_URL=supabase-database-url:latest \
  --project recipe-chatbot-499108
```

Public access requires the Cloud Run Invoker role:

```bash
gcloud run services add-iam-policy-binding recipe-chatbot-web \
  --region asia-northeast1 \
  --project recipe-chatbot-499108 \
  --member=allUsers \
  --role=roles/run.invoker
```

## Deep Agent Job

The Deep Agent job can be executed manually for smoke testing:

```bash
gcloud run jobs execute recipe-deep-agent \
  --region asia-northeast1 \
  --update-env-vars DEEP_AGENT_QUERY="tonjiru recipe technique",DEEP_AGENT_MAX_PAGES=2 \
  --wait \
  --project recipe-chatbot-499108
```

Cloud Storage output is written under:

```text
gs://recipe-robot/recipe-chatbot/web_recipe_reference/
gs://recipe-robot/recipe-chatbot/results/
```

## Useful Commands

Check recent builds:

```bash
gcloud builds list --project recipe-chatbot-499108 --limit=5
```

Check Cloud Run Service:

```bash
gcloud run services describe recipe-chatbot-web \
  --region asia-northeast1 \
  --project recipe-chatbot-499108
```

Check Cloud Run Job:

```bash
gcloud run jobs describe recipe-deep-agent \
  --region asia-northeast1 \
  --project recipe-chatbot-499108
```

View app logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="recipe-chatbot-web"' \
  --project recipe-chatbot-499108 \
  --limit=50
```

## Project Structure

```text
app.py                         # Streamlit frontend
app/cloud_run_jobs.py          # Cloud Run Job invocation helper
app/config.py                  # Runtime configuration
app/database.py                # SQLAlchemy tables and persistence
app/deep_agent.py              # Agentic crawler and reference collection
app/deep_agent_job.py          # Cloud Run Job entrypoint
app/gcs_storage.py             # Cloud Storage helper
app/json_output.py             # Structured JSON generation
app/openrouter.py              # OpenRouter free-model gateway
app/rag_chatbot.py             # RAG pipeline
app/scraper.py                 # Recipe page extraction
docker/Dockerfile              # Cloud Run compatible image
docker/docker-compose.yml      # Local Docker Compose stack
scripts/init_db.py             # Database initialization
scripts/rebuild_index.py       # RAG index rebuild
cloudbuild.yaml                # Cloud Build CI/CD pipeline
```

## Security Notes

- Do not commit `.env`.
- Store production secrets in Google Secret Manager.
- Use URL encoding for special characters in database passwords.
- OpenRouter model IDs must end with `:free`; the app rejects non-free model IDs.
- Rotate any API key or database password that has appeared in chat, logs, screenshots, or commits.

## License

No license has been declared yet.
