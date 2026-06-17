# CODEX Project Notes

このファイルは、次にこのリポジトリで作業するCodexがシステムをすばやく理解し、安全にコードを書くための開発メモです。READMEよりも「現在の実装判断」「変更履歴」「注意点」を優先します。

## Current System

Recipe RAG Chatbotは、Streamlit UI、LangChain、TurboVec、FastEmbed、Qwen/Gemini、mem0、PostgreSQL、crawl4aiで構成されています。

主なユーザー導線:

- `Qwen RAG Chat`: Qwen + RAG。現在のメイン動線。
- `Gemini RAG Chat`: Gemini + RAG。
- `Qwen Chat`: RAGなしのQwen単体。
- `Gemini Chat`: RAGなしのGemini単体。
- `past conversation`: PostgreSQLにJSONB保存された過去会話の閲覧。
- `Crawl4AI Check`: crawl4ai LLM extractionの性能確認。
- `Adaptive Crawl`: crawl4ai Adaptive Crawlingによるサイト内調査。

削除済みUI:

- `JSON + PostgreSQL`
- `DB DataFrame`

`app/json_output.py` と `app/view_db_dataframe.py` はまだ残っているが、現在のStreamlit sidebarには出していない。必要になるまでUIへ戻さない。

## Architecture

### Frontend

- Entry point: `app.py`
- Streamlit app全体を `main()` が制御する。
- Sidebarのmode選択で表示ページを切り替える。
- Runtime errorは `app/error_logger.py` 経由で `ERROR_LOG.md` に追記される。
- Chatbot resourceは `st.cache_resource` でキャッシュする。
  - `load_chatbot()`: shared RAG chatbot
  - `load_qwen_chatbot()`: Qwen専用RAG chatbot
  - キャッシュ済み古いインスタンス対策として `ensure_rag_chatbot_capabilities()` がある。

### LLM Layer

- `app/llm.py`
  - `build_qwen_llm()`: Ollama OpenAI-compatible API経由でQwenを呼ぶ。
  - `build_gemini_llm()`: Gemini API。
  - `build_chat_llm()`: backend名からLLMを選択。
  - `strip_hidden_reasoning()`: Qwen3系の `<think>...</think>` をUI/JSON parser前に除去。

Qwen/Geminiの出力は、ユーザーの最新質問の言語に合わせるようプロンプトで明示している。

### RAG

- Main implementation: `app/rag_chatbot.py`
- Qwen-specific wrapper: `app/qwen.py`
- Vector store: TurboVec under `data/turbovec_index/`
- Embeddings: FastEmbed, default `BAAI/bge-small-en-v1.5`
- Source directories:
  - `data/joc_pages/`
  - `data/web_recipe_reference/`
- `load_just_one_cookbook_docs()` はローカル保存文書を優先し、なければJust One Cookbook live fetchへ進む。
- Just One CookbookはPython request/crawlerに403や空抽出を返すことがあるため、ローカル保存ファイルとDeep Agent収集が重要。

RAG回答の現在の判断フロー:

1. Retrieverで関連chunkを取得。
2. LangChain chainで「取得文脈が質問に直接答えるのに十分か」をYES/NO判定。
3. 十分なら `answer_from_docs()` で通常RAG回答。
4. 不十分ならUI内で「Deep Agentで探しますか？ Yes / No」と聞く。
5. Yesなら既存Deep AgentでWeb収集、保存、index rebuild、RAG回答。
6. Noなら `answer_from_model_knowledge()` でLLM自身の一般知識から回答。

この分岐は、だし巻き卵の質問に対して卵焼きのRAG文脈だけが返り、モデルが回答を控えてしまった問題を改善するために追加された。

### Deep Agent / Crawling

- `app/deep_agent.py`
  - crawl4ai Agentic Crawler。
  - LLMで検索クエリ、crawl keywords、seed URLを作る。
  - DuckDuckGo HTML検索から候補URLを集める。
  - Best-first crawlでページを収集し、`data/web_recipe_reference/` に保存する。
- Sidebarから手動実行できる。
- Chatbot内からも、RAG文脈不足時のYes分岐で実行される。

Deep Agentの2つの用途:

- Sidebarの「Deep Agent自動収集」: ユーザーが明示的に参照データを増やす。
- Chatbot内Deep Agent: RAGで情報不足と判定された時に、回答前にユーザーへYes/No確認してから追加調査する。

### Memory

- `app/memory.py`
- mem0はユーザーの好み、制約、会話継続性のlong-term memory用。
- mem0は研究用の閲覧UIには使わない。
- 過去会話閲覧はPostgreSQLの `chat_conversations` を使う。

### PostgreSQL

- `app/database.py`
- `DATABASE_URL` は `.env` から読む。
- `scripts/init_db.py` で `metadata.create_all()` を実行できる。

Tables:

- `proposed_recipes`
  - 旧JSON recipe proposal保存用。
  - 現在UIでは使っていないが、互換のため残している。
- `chat_conversations`
  - 研究用の過去会話保存。
  - `ai_type`: `Gemini`, `Gemini_RAG`, `Qwen`, `Qwen_RAG`
  - `messages`: JSONB。`[{role, content}, ...]`
  - `raw_json`: JSONB。AI種別とmessagesを含む。
  - `created_at`, `updated_at`

会話保存:

- `persist_current_conversation()` が各チャットUIから呼ばれる。
- 同一Streamlit sessionでは、各チャット種別ごとにconversation idをsession_stateへ保持し、DB rowをupdateする。
- DB保存失敗時もチャット自体は止めず、`ERROR_LOG.md` に記録する。

過去会話閲覧:

- Sidebar mode: `past conversation`
- 一覧では3項目を横並び表示:
  - Date
  - Conversation
  - AI
- 「この会話を見る」ボタンで詳細へ遷移。
- 詳細は `st.chat_message()` で、現在のチャットに近い会話形式で表示する。

## Important Files

- `app.py`: Streamlit UI、mode切り替え、chat state、会話DB保存、past conversation表示。
- `app/rag_chatbot.py`: shared RAG pipeline、context sufficiency判定、RAG回答、model knowledge fallback。
- `app/qwen.py`: Qwen-only helper、Qwen RAG pipeline。
- `app/llm.py`: Qwen/Gemini builder、hidden reasoning除去。
- `app/deep_agent.py`: crawl4ai Agentic Crawler。
- `app/adaptive_crawler.py`: Adaptive Crawling調査とLLM synthesis。
- `app/crawl4ai_performance.py`: crawl4ai LLM extraction検証。
- `app/database.py`: PostgreSQL schema and persistence。
- `app/memory.py`: mem0 long-term memory。
- `app/scraper.py`: Just One Cookbook page extraction and local save。
- `scripts/rebuild_index.py`: TurboVec index rebuild。
- `scripts/init_db.py`: PostgreSQL table creation。
- `ERROR_LOG.md`: Runtime error history。

## Recent Change History

### 2026-06-17

- Cloud Run migration:
  - Web app is deployed as Cloud Run Service `recipe-chatbot-web`.
  - Deep Agent is deployed as Cloud Run Job `recipe-deep-agent`.
  - Collected recipe references and job status are stored in Cloud Storage bucket `recipe-robot` under prefix `recipe-chatbot`.
  - Production DB is Supabase Postgres via `DATABASE_URL` Secret Manager entry `supabase-database-url`.
  - `openrouter-api-key` Secret Manager entry must contain the full `sk-or-...` key. A previous broken version missed the leading `s`, causing Cloud Run Job logs to show `Missing Authentication header` before any search happened.
- Error logging:
  - `app/error_logger.py` still appends local `ERROR_LOG.md`.
  - When `GCS_BUCKET` is configured, the same entries are also synced to `gs://<bucket>/<prefix>/ERROR_LOG.md` because Cloud Run filesystem writes are ephemeral.
  - Deep Agent Job exceptions now call `log_error()` before writing failed job status.
- RAG missing-data permission flow:
  - If no usable recipe data/vector index exists, `OpenRouter RAG Chat` no longer stops with only a warning.
  - The UI now asks for explicit permission with buttons: `Deep Agentを実行` / `実行しない`.
  - Approval starts Deep Agent. On Cloud Run this starts a Cloud Run Job and stores pending state; the user refreshes job status, then the app rebuilds the RAG index and answers from collected data.
  - Denial ends the current answer flow and recommends Deep Agent data collection instead of falling back to unsupported general knowledge.
- Deep Agent robustness:
  - If crawl4ai best-first crawling finds no page with enough text, `app/deep_agent.py` now falls back to direct HTTP fetch + BeautifulSoup text extraction for selected/candidate URLs.
  - This was added after Cloud Run Job reached Crawl4AI but failed with `Agentic Crawler did not save any pages`.
- Past conversation time:
  - `past conversation` now displays UTC-naive DB timestamps as JST using `format_display_datetime()`.
  - Existing DB rows are assumed UTC because the app has historically written `datetime.utcnow()`.

### 2026-06-05

- Qwen/Gemini output language alignment:
  - Qwen-only, Qwen RAG, shared RAG, JSON output, crawl4ai extraction, Adaptive synthesisで、ユーザー入力言語に合わせる指示を追加。
- RAG sufficiency decision:
  - Retriever結果が質問に直接答えるのに十分かをLangChain chainでYES/NO判定。
  - 不十分な場合、chat UIでDeep Agent実行のYes/No確認を追加。
  - Yes: Deep Agent収集、DB/index更新、RAG回答。
  - No: LLM自身の一般知識で回答。
- Streamlit cache recovery:
  - 古い `QwenRAGChatbot` cacheが `retrieve()` を持たず `AttributeError` になったため、必要メソッドがない場合にcache clearしてreloadする `ensure_rag_chatbot_capabilities()` を追加。
- Past conversation:
  - `chat_conversations` PostgreSQL tableを追加。
  - 4つのチャット種別をJSONBで保存。
  - Sidebarに `past conversation` modeを追加。
  - `JSON + PostgreSQL` と `DB DataFrame` のUI modeを削除。

## Current Caveats

- READMEは一部古い。特にJSON+PostgreSQL/DataFrame UIの説明は現在のsidebarと一致しない可能性がある。
- `ERROR_LOG.md` は開発中のログで、今回の作業でも変更状態になっていることがある。通常はユーザーの明示がなければ消さない。
- `README.md` も作業前から変更状態だった。無関係なら触らない。
- CodeGraphはこのプロジェクトで未初期化だった。構造探索では通常の `rg` / `sed` を使った。
- PostgreSQL実接続は環境依存。コード変更時は少なくとも `python -m py_compile ...` と `metadata.tables` 確認を行う。
- Deep AgentはWeb検索/クロール/LLMを使うため時間がかかり、ネットワークやサイト側制限に影響される。
- Just One Cookbookからのlive fetchは403または抽出0文字になりやすい。`data/joc_pages/` と `data/web_recipe_reference/` のローカル文書を優先する設計を維持する。

## Verification Commands

よく使う確認:

```bash
python -m py_compile app.py app/database.py app/qwen.py app/rag_chatbot.py
python -c "from app.database import metadata; print(sorted(metadata.tables))"
python scripts/init_db.py
python scripts/rebuild_index.py
```

Streamlit:

```bash
streamlit run app.py
```

Docker:

```bash
docker compose -f docker/docker-compose.yml up --build
```

## Development Guidance

- ユーザー変更を巻き戻さない。特に `README.md` と `ERROR_LOG.md` は変更済みであることが多い。
- UI modeを増減する時は、sidebar listと `main()` の分岐を必ず同時に更新する。
- チャット履歴を変更する時は、PostgreSQL保存の `persist_current_conversation()` も忘れずに更新する。
- Qwen出力は必ず `strip_hidden_reasoning()` を通す。
- RAGプロンプトを強くしすぎると、検索結果がずれた時に回答不能になりやすい。現在はcontext sufficiency判定とDeep Agent/LLM knowledge fallbackで吸収する。
- DB schemaを増やす時は `metadata` にTableを追加し、`scripts/init_db.py` で作成できる状態にする。
