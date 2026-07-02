# Recipe Chatbot Project Skill

Use this file as the working skill for this repository. It is optimized for fast, low-risk development of the Recipe RAG Chatbot while keeping Google Cloud usage inside the free tier when possible, and under about 500 JPY/month when cloud deployment is necessary.

## Mission

Build and maintain a Japanese home-cooking recipe assistant with:

- Streamlit UI
- OpenRouter free-model chat and RAG
- local FastEmbed + TurboVec retrieval
- Supabase Postgres conversation history
- Cloud Run Service for the web app
- Cloud Run Job for Deep Agent crawling
- Cloud Storage for Cloud Run runtime artifacts

Prefer local development and small verification loops. Treat cloud deploys, Cloud Build runs, Cloud Run Job executions, and long browser sessions as budgeted actions.

## Cost Guardrails

Default target: stay within Google Cloud free tier. Hard working target: keep Google Cloud spend under 500 JPY/month.

Before any action that may cost money:

1. Say what resource will be used.
2. Prefer local checks first.
3. Avoid repeated Cloud Build deploy loops.
4. Avoid unnecessary Cloud Run Job executions.
5. Keep generated storage small.

Current known Google Cloud project:

- Project: `recipe-chatbot-499108`
- Region: `asia-northeast1`
- Web service: `recipe-chatbot-web`
- Deep Agent job: `recipe-deep-agent`
- Artifact Registry repo: `recipe-chatbot`
- GCS bucket: `recipe-robot`
- GCS prefix: `recipe-chatbot`
- Public URL: `https://recipe-chatbot-web-bvyktzzbcq-an.a.run.app/`

Current billing observations from 2026-07-02 checks:

- Billing is enabled for `recipe-chatbot-499108`.
- Cloud Run Service exists and is Ready.
- Cloud Run Job exists and had 8 executions.
- Cloud Build had 7 builds; measured successful/cancelled build time was roughly 42 minutes.
- GCS bucket usage was only about `1.74MiB`.
- Artifact Registry had 6 Docker images.
- Cloud Scheduler and Compute Engine APIs were disabled, so no scheduled job or VM always-on spend was found.
- No BigQuery Billing Export dataset was found, so exact JPY spend must be confirmed in Google Cloud Console Billing Reports.

Cost-sensitive defaults:

- Use OpenRouter models ending in `:free` only.
- Keep `GCS_BUCKET` empty for local-only development unless testing Cloud Run behavior.
- Run Deep Agent with very small limits during tests, such as `DEEP_AGENT_MAX_PAGES=1` or `2`.
- Do not enable Cloud Scheduler, Compute Engine, BigQuery export, Cloud Billing Budget API, or other paid-adjacent APIs just to inspect state unless the user approves.
- Do not delete cloud resources without explicit user approval.

Cloud Run cost notes:

- The service currently has no observed `minScale`, so idle instances that are not minimum instances should not create idle compute charges.
- Browser sessions can keep Streamlit websocket requests open and create billed Cloud Run active time.
- Cloud Run Job is billed while executions run, including failed executions.
- Cloud Build consumes build minutes even for cancelled/failed builds after they start.
- Artifact Registry and Cloud Storage can create small ongoing storage charges, though current usage appears small.

## Development Workflow

Start every task with local context:

```bash
git status --short
rg --files
```

Use CodeGraph for structural questions if available. Use `rg` for literal text and logs.

Respect dirty worktrees:

- Do not revert user changes.
- `ERROR_LOG.md` is often modified by runtime logging; do not clean it unless asked.
- `data/openrouter_active_model.txt` is runtime state and normally should not be committed.

For code changes:

1. Read the nearest implementation files.
2. Make the smallest change that matches existing patterns.
3. Run local syntax/import checks.
4. Only deploy to Cloud Run when the user asks or when deployment is the actual task.

Useful local verification:

```bash
python -m py_compile app.py app/database.py app/rag_chatbot.py app/openrouter.py app/deep_agent.py app/cloud_run_jobs.py
python -c "from app.database import metadata; print(sorted(metadata.tables))"
python scripts/init_db.py
python scripts/rebuild_index.py
```

Run locally:

```bash
streamlit run app.py
```

Docker check:

```bash
docker compose -f docker/docker-compose.yml up --build
```

## Architecture Map

Important files:

- `app.py`: Streamlit entrypoint, sidebar modes, chat state, conversation persistence, Deep Agent UI.
- `app/config.py`: environment configuration.
- `app/llm.py`: LLM builders and hidden reasoning stripping.
- `app/openrouter.py`: OpenRouter free-model gateway and error handling.
- `app/rag_chatbot.py`: shared RAG pipeline, context sufficiency, fallback behavior.
- `app/deep_agent.py`: crawl4ai/DuckDuckGo agentic crawling and local reference writing.
- `app/deep_agent_job.py`: Cloud Run Job entrypoint.
- `app/cloud_run_jobs.py`: Cloud Run Job API trigger helper.
- `app/gcs_storage.py`: GCS-backed runtime state for Cloud Run.
- `app/database.py`: SQLAlchemy schema and persistence.
- `app/error_logger.py`: local and GCS error logging.
- `scripts/rebuild_index.py`: TurboVec index rebuild.
- `scripts/init_db.py`: PostgreSQL table creation.
- `cloudbuild.yaml`: Cloud Build deploys both web service and job.
- `docker/Dockerfile`: Cloud Run image.
- `ERROR_LOG.md`: runtime error history; read it, do not casually rewrite it.

Current UI modes:

- `OpenRouter RAG Chat`
- `OpenRouter Chat`
- `past conversation`
- `Crawl4AI Check`
- `Adaptive Crawl`

Old UI modes removed from sidebar:

- `JSON + PostgreSQL`
- `DB DataFrame`

The old helper files may remain for compatibility, but do not re-add UI entries unless the task asks for them.

## RAG And Chat Rules

The main chat path is OpenRouter + RAG.

Keep these behavior rules:

- OpenRouter model IDs must end with `:free`.
- The app should reject non-free model IDs.
- Qwen-style hidden reasoning, such as `<think>...</think>`, must be stripped before UI display or JSON parsing.
- Answer language should follow the user's latest question language.
- If retrieved context is insufficient, ask before launching Deep Agent.
- If the user declines Deep Agent, avoid presenting unsupported recipe claims as RAG-grounded facts.

RAG data sources:

- `data/joc_pages/`
- `data/web_recipe_reference/`
- Cloud Run/GCS equivalent under `gs://recipe-robot/recipe-chatbot/`

Just One Cookbook live fetch is fragile. It has previously returned 403 or empty extraction, so prefer local saved documents and Deep Agent-collected references.

## Deep Agent Rules

Deep Agent is useful but cost- and time-sensitive.

Use it when:

- RAG context is missing.
- The user explicitly approves additional collection.
- A task requires fresh recipe references.

Avoid it when:

- A local unit/syntax check is enough.
- The question can be answered from existing data.
- The user is trying to minimize cloud/API use.

Cloud Run behavior:

- Web app starts `recipe-deep-agent` instead of running long crawling inside Streamlit.
- Job status is persisted so the user can refresh and continue.
- Job writes collected references and status into GCS when `GCS_BUCKET` is configured.

Known failure lessons:

- `Missing Authentication header` in Cloud Run Job meant the Secret Manager value for `openrouter-api-key` was malformed; it must include the full `sk-or-...` key.
- `Agentic Crawler did not save any pages` led to adding direct HTTP + BeautifulSoup fallback.
- `OpenRouterRateLimitError: Provider returned error` can occur even with free models; surface it cleanly and avoid retry storms.
- Missing `google-cloud-storage` caused local runs with `GCS_BUCKET` set to fail. For local development, leave `GCS_BUCKET` empty unless testing GCS.

## Database Rules

Postgres is used for conversation history.

Tables:

- `chat_conversations`
  - `ai_type`
  - `messages` JSONB
  - `raw_json` JSONB
  - `created_at`
  - `updated_at`
- `proposed_recipes`
  - legacy JSON recipe proposal table; keep for compatibility.

When changing chat flow:

- Keep `persist_current_conversation()` aligned.
- Do not let DB failures break chat; log and continue.
- Display UTC-naive DB timestamps as JST in `past conversation`.

For schema changes:

```bash
python -c "from app.database import metadata; print(sorted(metadata.tables))"
python scripts/init_db.py
```

## Cloud Deployment Runbook

Deploy only when needed. Each push to `main` can trigger Cloud Build and Cloud Run deployment.

Manual preflight:

```bash
git status --short
git branch --show-current
python -m py_compile app.py app/database.py app/rag_chatbot.py app/openrouter.py app/deep_agent.py app/cloud_run_jobs.py
```

Check latest builds:

```bash
gcloud builds list \
  --project recipe-chatbot-499108 \
  --limit 5 \
  --format='table(id,status,createTime,source.repoSource.branchName,substitutions.SHORT_SHA)'
```

Check a build:

```bash
gcloud builds describe <BUILD_ID> \
  --project recipe-chatbot-499108 \
  --format='yaml(status,startTime,finishTime,logUrl,statusDetail,failureInfo)'
```

Check Cloud Run service:

```bash
gcloud run services describe recipe-chatbot-web \
  --project recipe-chatbot-499108 \
  --region asia-northeast1 \
  --format='yaml(status.url,status.latestReadyRevisionName,status.conditions,spec.template.spec.containers[0].image,spec.template.spec.containers[0].resources,spec.template.metadata.annotations)'
```

Check revisions:

```bash
gcloud run revisions list \
  --service recipe-chatbot-web \
  --project recipe-chatbot-499108 \
  --region asia-northeast1 \
  --format='table(metadata.name,status.conditions[0].type,status.conditions[0].status,status.imageDigest)' \
  --limit 5
```

Check job:

```bash
gcloud run jobs describe recipe-deep-agent \
  --project recipe-chatbot-499108 \
  --region asia-northeast1
```

Check job executions:

```bash
gcloud run jobs executions list \
  --job recipe-deep-agent \
  --project recipe-chatbot-499108 \
  --region asia-northeast1 \
  --format='table(metadata.name,status.completionTime,status.conditions[0].type,status.conditions[0].status)'
```

Check recent Cloud Run logs:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="recipe-chatbot-web"' \
  --project recipe-chatbot-499108 \
  --limit 50 \
  --format='table(timestamp,severity,textPayload)'
```

## Cost Check Commands

Use these before/after cloud-heavy work.

Billing link state:

```bash
gcloud billing projects describe recipe-chatbot-499108 \
  --format='yaml(billingAccountName,billingEnabled,name,projectId)'
```

Cloud Run service count:

```bash
gcloud run services list \
  --region asia-northeast1 \
  --project recipe-chatbot-499108 \
  --format='table(metadata.name,status.url,status.conditions[0].status)'
```

Cloud Run job count:

```bash
gcloud run jobs list \
  --region asia-northeast1 \
  --project recipe-chatbot-499108 \
  --format='table(metadata.name,status.executionCount,status.latestCreatedExecution.completionTime)'
```

GCS usage:

```bash
gcloud storage du --summarize --readable-sizes gs://recipe-robot
```

Artifact Registry images:

```bash
gcloud artifacts docker images list \
  asia-northeast1-docker.pkg.dev/recipe-chatbot-499108/recipe-chatbot \
  --include-tags \
  --project recipe-chatbot-499108 \
  --format='table(package,tags,version,updateTime)'
```

Cloud Build usage:

```bash
gcloud builds list \
  --project recipe-chatbot-499108 \
  --limit 20 \
  --format='table(id,status,createTime,images)'
```

Exact money spent:

- Prefer Google Cloud Console Billing Reports.
- If Billing Export is not configured, CLI cannot reliably report final JPY charges.
- Do not enable new billing/export APIs just to answer casual cost questions unless the user approves.

## Cloud Run Resource Policy

The app has exceeded smaller memory limits:

- 512MiB failed around 531MiB.
- 2Gi failed around 2408MiB.
- 4Gi failed around 4119MiB.

Current web deploy should stay:

- `--memory=8Gi`
- `--cpu=2`
- `--concurrency=1`

Reason: RAG, embeddings, and index loading are memory-heavy. Lowering memory may look cheaper but causes crashes, retries, and wasted debugging time.

Do not add `minScale` unless the user explicitly accepts idle-cost risk.

## Common Incidents

Public URL does not show latest feature:

- Confirm the change reached `main`; feature branch pushes alone do not deploy.
- Wait for Cloud Build `SUCCESS`.
- Confirm Cloud Run latest Ready revision uses the expected image.
- Reload or test in a clean browser session.

Prompt send freezes and UI resets:

- Check Cloud Run logs for memory exceeded.
- Keep service at 8Gi/2CPU/concurrency 1.

Gemini `RESOURCE_EXHAUSTED`:

- Free Gemini quota was hit in earlier development.
- Prefer OpenRouter `:free` model flow.

GCS errors locally:

- If local run says `Install google-cloud-storage to use GCS_BUCKET storage`, either install the dependency or unset `GCS_BUCKET`.
- For normal local work, unset `GCS_BUCKET`.

Cloud Run Job fails before search:

- Check `OPENROUTER_API_KEY` Secret Manager value.
- Confirm it starts with `sk-or-`.

Deep Agent saves no pages:

- Keep fallback HTTP extraction.
- Test with small `max_pages`.
- Avoid assuming a target site allows crawler extraction.

## PR And Commit Hygiene

Before handing off:

```bash
git status --short
python -m py_compile app.py app/database.py app/rag_chatbot.py app/openrouter.py app/deep_agent.py app/cloud_run_jobs.py
```

Mention if not run:

- DB migrations or real DB connection checks
- Docker build
- Cloud Build
- Cloud Run deploy
- Deep Agent Cloud Run Job

Do not include runtime artifacts in commits unless explicitly requested:

- `ERROR_LOG.md` changes from incidental local runs
- `data/openrouter_active_model.txt`
- generated crawl/reference data
- local vector indexes

When a deployment is requested, summarize:

- Git commit/branch
- Cloud Build ID and status
- Cloud Run revision
- Public URL verification
- Any expected cost impact

