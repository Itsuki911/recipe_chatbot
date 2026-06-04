# Error Log

このファイルは開発中に発生したエラーをCodexが後から確認するためのログです。
ユーザーが毎回チャットにエラー全文を貼らなくても、Codexはこのファイルを読めば過去のエラー内容・発生日・発生時刻を確認できます。

## Logging Policy

- Streamlit UI操作中に捕捉した例外は `app/error_logger.py` から自動追記されます。
- `RuntimeError`, `ImportError`, `ValueError`, DB接続エラー、スクレイピングエラー、チャット回答生成エラーなどは、UI側で捕捉されるとこのファイルに記録されます。
- 会話中の回答生成エラーは `Chat conversation response generation` として、対象のユーザー質問と一緒に記録されます。
- `app.py` の最上位 `try/except` により、未処理の通常例外も `Unhandled Streamlit UI error` として記録されます。
- Pythonプロセス自体が起動できない構文エラーや、`app.config` / `app.error_logger` のimport前に起きる致命的エラーは、このファイルに自動記録できない場合があります。

## 2026-05-29 13:17:25 JST

- Context: Streamlit server startup
- Error Type: PermissionError
- Message: `[Errno 1] Operation not permitted`
- Cause: sandbox内で `python -m streamlit run app.py --server.port 8501 --server.headless true` がlocalhost bindできなかった。
- Resolution: escalated permissionでStreamlitを起動した。

## 2026-05-29 13:18 JST

- Context: Just One Cookbook document loading
- Error Type: RuntimeError
- Message: `No recipe documents could be loaded from Just One Cookbook.`
- Cause: `data/joc_pages/` にレシピ文書がなく、Python `requests` からJust One Cookbookへアクセスできなかった。
- Resolution: `data/joc_pages/` のローカルfallbackを追加し、Streamlit側でRuntimeErrorを捕まえて対処法を表示するようにした。

## 2026-05-29 13:20 JST

- Context: Just One Cookbook web request
- Error Type: HTTPError / ConnectionError
- Message: `403 Forbidden` または `Failed to resolve 'www.justonecookbook.com'`
- Cause: Just One CookbookがPythonの自動取得を拒否、または実行環境からDNS解決できなかった。
- Resolution: ブラウザ保存した `.html`, `.txt`, `.md` を `data/joc_pages/` に置く運用を追加した。

## 2026-05-29 13:30 JST

- Context: Deep Agents dependency installation
- Error Type: No matching distribution found
- Message: `deepagents>=0.1.0` requires Python 3.11+, current local Python is 3.10.
- Cause: ローカル環境のPythonバージョンがDeep Agentsの要求より低い。
- Resolution: `requirements.txt` で `deepagents>=0.1.0; python_version >= "3.11"` に変更し、アプリ側でPython 3.11以上が必要と表示するようにした。

## 2026-05-29 JST

- Context: Streamlit import-time startup
- Error Type: ImportError
- Message: `cannot import name 'LOCAL_RECIPE_DIR' from 'app.config'`
- Cause: `app.py` のトップレベルで `LOCAL_RECIPE_DIR` をimportしていたため、Streamlitが古い/不完全な `app.config` を読んだ場合にアプリ本体とロガーが起動前に落ちた。
- Resolution: `app.py` と `app/error_logger.py` にimport-time fallbackを追加し、同種の起動直後エラーでも最低限ログへ追記できるようにした。Streamlitプロセスの再起動も必要。

## 2026-05-29 14:30:32 JST

- Context: Unhandled Streamlit UI error
- Error Type: ImportError
- Message: `cannot import name 'LOCAL_RECIPE_DIR' from 'app.config'`
- Cause: `app/scraper.py` と `app/rag_chatbot.py` が `from app.config import LOCAL_RECIPE_DIR` のような直接importに依存していた。Streamlitの再読み込み時に古い/不完全な `app.config` を見た場合、サイドバー描画時に落ちる。
- Resolution: `app/scraper.py` と `app/rag_chatbot.py` を `from app import config as app_config` + `getattr(..., fallback)` に変更し、config属性が一時的に欠けても起動できるようにした。

## 2026-05-29 14:30:32 JST

- Context: Unhandled Streamlit UI error
- Error Type: ImportError
- Message: cannot import name 'LOCAL_RECIPE_DIR' from 'app.config' (/Users/adachiitsuki/Desktop/recipe_chatbot/app/config.py)
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 214, in <module>
    main()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 201, in main
    force_rebuild, mode = render_sidebar()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 67, in render_sidebar
    from app.scraper import run_deep_agent_recipe_collection, save_recipe_page_from_url
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 13, in <module>
    from app.config import JOC_START_URL, LOCAL_RECIPE_DIR, OPENAI_API_KEY, OPENAI_MODEL
ImportError: cannot import name 'LOCAL_RECIPE_DIR' from 'app.config' (/Users/adachiitsuki/Desktop/recipe_chatbot/app/config.py)
```

## 2026-05-29 JST

- Context: Streamlit app startup
- Status: Resolved
- Message: アプリを無事起動できた。
- Notes: `LOCAL_RECIPE_DIR` ImportError対策後、ユーザー側で起動成功を確認。
## 2026-05-29 14:36:18 JST

- Context: Recipe source loading
- Error Type: RuntimeError
- Message: No recipe documents could be loaded from Just One Cookbook.
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 140, in render_chat
    chatbot = load_chatbot(should_rebuild)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 280, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 325, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 384, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 34, in load_chatbot
    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 210, in __init__
    if len(doc.page_content) > 500:
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 180, in build_or_load_vector_store
    soup = bs4.BeautifulSoup(raw, "html.parser")
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 157, in load_just_one_cookbook_docs
    break
RuntimeError: No recipe documents could be loaded from Just One Cookbook.
```
## 2026-05-29 14:39:51 JST

- Context: Sidebar Deep Agent collection
- Error Type: RuntimeError
- Message: LangChain Deep Agents requires Python 3.11 or newer. Current Python is 3.10. Use the URL保存 feature on Python 3.10, or create a Python 3.11 environment for Deep Agent collection.
- Python: 3.10.12

### Details

```text
query=Kitsune Udon, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 104, in render_sidebar
    saved_pages = run_deep_agent_recipe_collection(deep_query, max_pages=deep_max_pages)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 108, in run_deep_agent_recipe_collection
    raise RuntimeError(
RuntimeError: LangChain Deep Agents requires Python 3.11 or newer. Current Python is 3.10. Use the URL保存 feature on Python 3.10, or create a Python 3.11 environment for Deep Agent collection.
```

## 2026-05-29 JST

- Context: UI error prevention
- Status: Improved
- Message: `No recipe documents could be loaded from Just One Cookbook.` と Python 3.10でのDeep Agent実行エラーを、例外発生前にUIで防止するようにした。
- Resolution: レシピデータ/FAISS indexが無い状態でChat/JSONを実行した場合は、RAG初期化を行わず、サイドバーからURL保存する案内を表示する。Python 3.11未満または `OPENAI_API_KEY` 未設定ではDeep Agentボタンをdisabledにする。

## 2026-05-29 JST

- Context: Import fallback path
- Status: Improved
- Message: `app.py` のimport fallbackで `data/` と `ERROR_LOG.md` の基準ディレクトリが1階層ずれる可能性を修正。
- Resolution: `app.py` はプロジェクトルート直下にあるため、fallback pathを `Path(__file__).resolve().parent` 基準に統一した。

## 2026-05-29 JST

- Context: Chat conversation response generation
- Error Type: ValueError
- Message: `device_map="auto"` requires `accelerate`.
- Cause: ローカルHugging Face/Gemmaモデルを `device_map="auto"` で読み込むために必要な `accelerate` が依存関係に入っていなかった。
- Resolution: `requirements.txt` に `accelerate>=0.34.0` を追加し、モデル読み込み前に不足時の説明つき `RuntimeError` を出すようにした。

## 2026-05-29 JST

- Context: Dependency installation
- Status: Resolved
- Message: `accelerate` をインストールし、`device_map="auto"` の前提依存を満たした。
- Verification: `accelerate 1.13.0` のimport確認と `python -m compileall app app.py scripts` が成功。

## 2026-05-29 JST

- Context: Docker dependency strategy
- Status: Improved
- Message: DockerでPython 3.11に固定できる構成を追加した。
- Resolution: `Dockerfile`, `docker-compose.yml`, `.dockerignore` を追加。Docker環境ではPython 3.11を使うため、`deepagents` のPython 3.11+要件を満たせる。PostgreSQLもComposeに含め、`data/` と `ERROR_LOG.md` をvolumeで永続化する。

## 2026-05-29 JST

- Context: Local Hugging Face model loading
- Status: Improved
- Message: 起動中プロセスが `accelerate` を認識できない場合でも、即座に `device_map="auto"` エラーへ落ちないようにした。
- Resolution: `accelerate` がimportできる場合のみ `device_map="auto"` を使い、無い場合はdevice_mapなしで読み込みを試す。最終的に失敗した場合はOpenAI backendまたはDocker環境を案内する説明つき `RuntimeError` を出す。
## 2026-05-29 14:43:41 JST

- Context: Chat conversation response generation
- Error Type: ValueError
- Message: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`
- Python: 3.10.12

### Details

```text
question=だし巻き卵の作り方を教えて
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 76, in _load
    self._model = AutoModelForImageTextToText.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/models/auto/auto_factory.py", line 387, in from_pretrained
    return model_class.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/modeling_utils.py", line 3998, in from_pretrained
    device_map = check_and_set_device_map(device_map)  # warn, error and fix the device map
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/integrations/accelerate.py", line 134, in check_and_set_device_map
    raise ValueError(
ValueError: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 192, in render_chat
    response = chatbot.answer(question)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 310, in answer
    answer = self.chain.invoke(question)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/runnables/base.py", line 3335, in invoke
    input_ = context.run(step.invoke, input_, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 381, in invoke
    self.generate_prompt(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 798, in generate_prompt
    return self.generate(prompt_strings, stop=stop, callbacks=callbacks, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 1028, in generate
    return self._generate_helper(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 824, in _generate_helper
    self._generate(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 1532, in _generate
    else self._call(prompt, stop=stop, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 88, in _call
    self._load()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 84, in _load
    self._model = AutoModelForCausalLM.from_pretrained(self.model_id, device_map="auto")
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/models/auto/auto_factory.py", line 387, in from_pretrained
    return model_class.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/modeling_utils.py", line 3998, in from_pretrained
    device_map = check_and_set_device_map(device_map)  # warn, error and fix the device map
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/integrations/accelerate.py", line 134, in check_and_set_device_map
    raise ValueError(
ValueError: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`
```

## 2026-05-29 15:25 JST

- Status: Resolved
- Context: Docker Compose startup
- Error: `Ports are not available: exposing port TCP 0.0.0.0:5432`
- Message: ローカル環境で既にPostgreSQLなどが `5432` を使用していたため、ComposeのDBコンテナが起動できなかった。
- Resolution: アプリ内部の `db:5432` 接続は維持し、ホスト公開ポートだけ `5433:5432` に変更した。VS Codeや外部DBツールから接続する場合は `localhost:5433` を使う。

## 2026-05-29 15:31 JST

- Status: Verified
- Context: Docker Compose application
- Message: `docker compose up -d` で `app` と `db` が起動した。`curl -I http://localhost:8501` は `HTTP/1.1 200 OK`、`pg_isready` は accepting connections、アプリコンテナから `init_db()` 実行は `db ok`。
- Note: Dockerイメージは約9.8GB。PyTorchがNVIDIA/CUDA系依存も取得しているため、ビルド時間と容量が大きい。必要ならDocker専用requirementsで軽量化を検討する。

## 2026-05-29 22:16 JST

- Status: Verified
- Context: Docker lightweight requirements
- Message: `requirements-docker.txt` を追加し、DockerfileをDocker専用requirementsでビルドするよう変更した。Composeでは `RAG_LLM_BACKEND=openai` と `RAG_EMBEDDING_BACKEND=openai` を指定し、PyTorch/Hugging Face依存をDockerから外した。
- Verification: 軽量イメージは約1.58GB。コンテナ内確認で `torch installed: False`, `transformers installed: False`, `rag imports ok`。`curl -I http://localhost:8501` は `HTTP/1.1 200 OK`、アプリコンテナからDB接続は `db ok`。
- Note: Docker軽量版でChat/JSON RAGを使うには `.env` の `OPENAI_API_KEY` が必要。

## 2026-05-29 22:51 JST

- Status: Verified
- Context: Gemini, TurboVec, mem0 Docker migration
- Message: OpenAI backend方針をやめ、Gemini 2.5 Flash (`gemini-2.5-flash`) をLangChain経由で使う構成へ変更した。Embeddingは無料ローカルのFastEmbed、Vector StoreはTurboVec、long-term memoryはmem0 + Qdrant local persistenceへ変更した。
- Verification: Docker build succeeded with `turbovec==0.6.0`, `mem0ai==2.0.4`, `fastembed==0.8.0`, `langchain-google-genai==4.2.4`。`curl -I http://localhost:8501` は `HTTP/1.1 200 OK`、DB接続は `db ok`。コンテナ内で `turbovec ok`, `mem0 ok`, `gemini langchain ok`, `fastembed ok`, `torch installed: False`, `transformers installed: False` を確認した。
- Note: `.env` はgitignore済み。実行時には `GOOGLE_API_KEY` が必要。チャットに貼ったAPIキーは漏洩済みとして再発行推奨。

## 2026-05-29 22:56 JST

- Status: Resolved
- Context: FastEmbed model selection
- Error: `Model intfloat/multilingual-e5-small is not supported in TextEmbedding`
- Message: FastEmbed 0.8.0では `intfloat/multilingual-e5-small` が対応モデル一覧になかった。また `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` はDocker内のHugging Face downloadが破損扱いで失敗した。
- Resolution: 無料でFastEmbed対応済みの `BAAI/bge-small-en-v1.5` に切り替えた。Just One Cookbookの保存テキストは英語中心なので、検索実用性とDocker安定性を優先した。
- Verification: Docker内でFastEmbed + TurboVecの最小vector作成と検索が成功し、`test` sourceを返した。`scripts/rebuild_index.py` で実データから `TurboVec index rebuilt from Just One Cookbook pages.` を確認した。

## 2026-05-29 23:01 JST

- Status: Action required
- Context: Gemini API runtime verification
- Error: `403 PERMISSION_DENIED`
- Message: Google Gemini APIが `.env` のAPI keyを `Your API key was reported as leaked. Please use another API key.` として拒否した。
- Resolution: アプリ側で「漏洩済みキー」と分かるUIメッセージを表示するようにした。`.env` は `.gitignore` と `.dockerignore` でGit/Docker build contextから除外済み。
- Follow-up: Google AI Studioで新しいAPI keyを再発行し、`.env` の `GOOGLE_API_KEY` を更新して `docker compose up -d` を実行する必要がある。

## 2026-05-29 23:10 JST

- Status: Verified
- Context: Gemini API key refresh and full RAG verification
- Message: `.env` に新しいGemini API keyが追加されたため、Docker Composeを再起動して再検証した。
- Verification: `.env` はgitignore済みかつGit未追跡。コンテナ内で `ChatGoogleGenerativeAI` / `gemini-2.5-flash` 初期化成功。RAG回答生成は `answer chars: 331`, `sources: 2` で成功。JSON生成とPostgreSQL保存も `database_id: 1` で成功。
- Memory Verification: mem0 long-term memoryの保存・検索も成功し、`User prefers low sugar tamagoyaki.` を検索で取得した。
- Resolution: Gemini APIの一時的な `503 UNAVAILABLE high demand` 対策として、RAG回答チェーンとJSON生成チェーンに3回リトライを追加した。
## 2026-05-29 14:47:48 JST

- Context: Chat conversation response generation
- Error Type: ValueError
- Message: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`
- Python: 3.10.12

### Details

```text
question=だし巻き卵の作り方を教えて
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 76, in _load
    except ImportError as exc:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/models/auto/auto_factory.py", line 387, in from_pretrained
    return model_class.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/modeling_utils.py", line 3998, in from_pretrained
    device_map = check_and_set_device_map(device_map)  # warn, error and fix the device map
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/integrations/accelerate.py", line 134, in check_and_set_device_map
    raise ValueError(
ValueError: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 192, in render_chat
    response = chatbot.answer(question)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 310, in answer
    }
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/runnables/base.py", line 3335, in invoke
    input_ = context.run(step.invoke, input_, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 381, in invoke
    self.generate_prompt(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 798, in generate_prompt
    return self.generate(prompt_strings, stop=stop, callbacks=callbacks, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 1028, in generate
    return self._generate_helper(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 824, in _generate_helper
    self._generate(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 1532, in _generate
    else self._call(prompt, stop=stop, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 88, in _call
    )
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 84, in _load
    self._model = AutoModelForImageTextToText.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/models/auto/auto_factory.py", line 387, in from_pretrained
    return model_class.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/modeling_utils.py", line 3998, in from_pretrained
    device_map = check_and_set_device_map(device_map)  # warn, error and fix the device map
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/integrations/accelerate.py", line 134, in check_and_set_device_map
    raise ValueError(
ValueError: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`
```
## 2026-05-29 14:53:03 JST

- Context: Chat conversation response generation
- Error Type: ValueError
- Message: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`
- Python: 3.10.12

### Details

```text
question=だし巻き卵の作り方を教えて
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 76, in _load
    except ImportError as exc:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/models/auto/auto_factory.py", line 387, in from_pretrained
    return model_class.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/modeling_utils.py", line 3998, in from_pretrained
    device_map = check_and_set_device_map(device_map)  # warn, error and fix the device map
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/integrations/accelerate.py", line 134, in check_and_set_device_map
    raise ValueError(
ValueError: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 192, in render_chat
    response = chatbot.answer(question)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 310, in answer
    - Do not mix up recipes with similar names.
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/runnables/base.py", line 3335, in invoke
    input_ = context.run(step.invoke, input_, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 381, in invoke
    self.generate_prompt(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 798, in generate_prompt
    return self.generate(prompt_strings, stop=stop, callbacks=callbacks, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 1028, in generate
    return self._generate_helper(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 824, in _generate_helper
    self._generate(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/llms.py", line 1532, in _generate
    else self._call(prompt, stop=stop, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 88, in _call
    **model_load_kwargs,
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 84, in _load
    self._processor = AutoProcessor.from_pretrained(self.model_id, padding_side="left")
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/models/auto/auto_factory.py", line 387, in from_pretrained
    return model_class.from_pretrained(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/modeling_utils.py", line 3998, in from_pretrained
    device_map = check_and_set_device_map(device_map)  # warn, error and fix the device map
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/transformers/integrations/accelerate.py", line 134, in check_and_set_device_map
    raise ValueError(
ValueError: Using a `device_map`, `tp_plan`, `torch.device` context manager or setting `torch.set_default_device(device)` requires `accelerate`. You can install it with `pip install accelerate`
```
## 2026-06-02 14:41:15 JST

- Context: Unhandled Streamlit UI error
- Error Type: ImportError
- Message: Could not import 'fastembed' Python package. Please install it with `pip install fastembed`.
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_community/embeddings/fastembed.py", line 95, in validate_environment
    fastembed = importlib.import_module("fastembed")
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/importlib/__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
  File "<frozen importlib._bootstrap>", line 1050, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1027, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1004, in _find_and_load_unlocked
ModuleNotFoundError: No module named 'fastembed'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 315, in <module>
    main()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 307, in main
    render_chat(force_rebuild)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 223, in render_chat
    chatbot = load_chatbot(should_rebuild)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 280, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 325, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 384, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 39, in load_chatbot
    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 365, in __init__
    self.vector_store = build_or_load_vector_store(force_rebuild=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 318, in build_or_load_vector_store
    embeddings = get_embeddings()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 271, in get_embeddings
    return FastEmbedEmbeddings(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/pydantic/main.py", line 250, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/pydantic/_internal/_decorators_v1.py", line 148, in _wrapper1
    return validator(values)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/utils/pydantic.py", line 184, in wrapper
    return func(cls, values)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_community/embeddings/fastembed.py", line 98, in validate_environment
    raise ImportError(
ImportError: Could not import 'fastembed' Python package. Please install it with `pip install fastembed`.
```
## 2026-06-02 14:42:35 JST

- Context: Unhandled Streamlit UI error
- Error Type: ModuleNotFoundError
- Message: No module named 'turbovec'
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 315, in <module>
    main()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 307, in main
    render_chat(force_rebuild)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 223, in render_chat
    chatbot = load_chatbot(should_rebuild)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 280, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 325, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 384, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 39, in load_chatbot
    return RecipeRAGChatbot(force_rebuild_index=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 365, in __init__
    self.vector_store = build_or_load_vector_store(force_rebuild=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/rag_chatbot.py", line 323, in build_or_load_vector_store
    from turbovec.langchain import TurboQuantVectorStore
ModuleNotFoundError: No module named 'turbovec'
```
## 2026-06-02 15:09:42 JST

- Context: JSON generation
- Error Type: OperationalError
- Message: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "recipe_user"

(Background on this error at: https://sqlalche.me/e/20/e3q8)
- Python: 3.10.12

### Details

```text
question=Please share a healthier high-protein version of dashi-maki tamago.
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 144, in __init__
    self._dbapi_connection = engine.raw_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3319, in raw_connection
    return self.pool.connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 448, in connect
    return _ConnectionFairy._checkout(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
    rec = pool._do_get()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 178, in _do_get
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    return self._create_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
    return _ConnectionRecord(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
    self.__connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/create.py", line 667, in connect
    return dialect.connect(*cargs_tup, **cparams)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/default.py", line 630, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
psycopg2.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "recipe_user"


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 274, in render_json_mode
    result = generate_recipe_json(question, save_to_db=True, force_rebuild_index=should_rebuild)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/json_output.py", line 76, in generate_recipe_json
    result["database_id"] = save_recipe_output(result, question=question, source_urls=source_urls)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/database.py", line 47, in save_recipe_output
    init_db(engine)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/database.py", line 37, in init_db
    metadata.create_all(engine)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/sql/schema.py", line 5930, in create_all
    bind._run_ddl_visitor(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3269, in _run_ddl_visitor
    with self.begin() as conn:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/contextlib.py", line 135, in __enter__
    return next(self.gen)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3259, in begin
    with self.connect() as conn:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3295, in connect
    return self._connection_cls(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 146, in __init__
    Connection._handle_dbapi_exception_noconnection(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 2450, in _handle_dbapi_exception_noconnection
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 144, in __init__
    self._dbapi_connection = engine.raw_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3319, in raw_connection
    return self.pool.connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 448, in connect
    return _ConnectionFairy._checkout(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
    rec = pool._do_get()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 178, in _do_get
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    return self._create_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
    return _ConnectionRecord(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
    self.__connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/create.py", line 667, in connect
    return dialect.connect(*cargs_tup, **cparams)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/default.py", line 630, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "recipe_user"

(Background on this error at: https://sqlalche.me/e/20/e3q8)
```
## 2026-06-02 15:09:54 JST

- Context: DB DataFrame view
- Error Type: OperationalError
- Message: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "recipe_user"

(Background on this error at: https://sqlalche.me/e/20/e3q8)
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 144, in __init__
    self._dbapi_connection = engine.raw_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3319, in raw_connection
    return self.pool.connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 448, in connect
    return _ConnectionFairy._checkout(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
    rec = pool._do_get()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 178, in _do_get
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    return self._create_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
    return _ConnectionRecord(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
    self.__connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/create.py", line 667, in connect
    return dialect.connect(*cargs_tup, **cparams)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/default.py", line 630, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
psycopg2.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "recipe_user"


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 293, in render_dataframe_mode
    df = recipes_dataframe()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/view_db_dataframe.py", line 9, in recipes_dataframe
    df = pd.DataFrame(fetch_recipes())
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/database.py", line 65, in fetch_recipes
    init_db(engine)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/database.py", line 37, in init_db
    metadata.create_all(engine)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/sql/schema.py", line 5930, in create_all
    bind._run_ddl_visitor(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3269, in _run_ddl_visitor
    with self.begin() as conn:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/contextlib.py", line 135, in __enter__
    return next(self.gen)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3259, in begin
    with self.connect() as conn:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3295, in connect
    return self._connection_cls(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 146, in __init__
    Connection._handle_dbapi_exception_noconnection(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 2450, in _handle_dbapi_exception_noconnection
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 144, in __init__
    self._dbapi_connection = engine.raw_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3319, in raw_connection
    return self.pool.connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 448, in connect
    return _ConnectionFairy._checkout(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
    rec = pool._do_get()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 178, in _do_get
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    return self._create_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
    return _ConnectionRecord(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
    self.__connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/create.py", line 667, in connect
    return dialect.connect(*cargs_tup, **cparams)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/default.py", line 630, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "recipe_user"

(Background on this error at: https://sqlalche.me/e/20/e3q8)
```
## 2026-06-02 15:17:00 JST

- Context: JSON generation
- Error Type: OperationalError
- Message: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5433 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
connection to server at "localhost" (::1), port 5433 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?

(Background on this error at: https://sqlalche.me/e/20/e3q8)
- Python: 3.10.12

### Details

```text
question=Please share a healthier high-protein version of dashi-maki tamago.
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 144, in __init__
    self._dbapi_connection = engine.raw_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3319, in raw_connection
    return self.pool.connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 448, in connect
    return _ConnectionFairy._checkout(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
    rec = pool._do_get()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 178, in _do_get
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    return self._create_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
    return _ConnectionRecord(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
    self.__connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/create.py", line 667, in connect
    return dialect.connect(*cargs_tup, **cparams)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/default.py", line 630, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
psycopg2.OperationalError: connection to server at "localhost" (127.0.0.1), port 5433 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
connection to server at "localhost" (::1), port 5433 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 274, in render_json_mode
    result = generate_recipe_json(question, save_to_db=True, force_rebuild_index=should_rebuild)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/json_output.py", line 76, in generate_recipe_json
    result["database_id"] = save_recipe_output(result, question=question, source_urls=source_urls)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/database.py", line 47, in save_recipe_output
    init_db(engine)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/database.py", line 37, in init_db
    metadata.create_all(engine)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/sql/schema.py", line 5930, in create_all
    bind._run_ddl_visitor(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3269, in _run_ddl_visitor
    with self.begin() as conn:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/contextlib.py", line 135, in __enter__
    return next(self.gen)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3259, in begin
    with self.connect() as conn:
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3295, in connect
    return self._connection_cls(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 146, in __init__
    Connection._handle_dbapi_exception_noconnection(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 2450, in _handle_dbapi_exception_noconnection
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 144, in __init__
    self._dbapi_connection = engine.raw_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/base.py", line 3319, in raw_connection
    return self.pool.connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 448, in connect
    return _ConnectionFairy._checkout(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
    rec = pool._do_get()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 178, in _do_get
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    return self._create_connection()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
    return _ConnectionRecord(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
    self.__connect()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
    with util.safe_reraise():
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/util/langhelpers.py", line 122, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/create.py", line 667, in connect
    return dialect.connect(*cargs_tup, **cparams)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/sqlalchemy/engine/default.py", line 630, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5433 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
connection to server at "localhost" (::1), port 5433 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?

(Background on this error at: https://sqlalche.me/e/20/e3q8)
```
## 2026-06-02 19:09:56 JST

- Context: Crawl4AI performance check
- Error Type: RuntimeError
- Message: ChatGoogleGenerativeAIError: Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-2.5-flash\nPlease retry in 4.01559499s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'model': 'gemini-2.5-flash', 'location': 'global'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '4s'}]}}
- Python: 3.10.12

### Traceback

```text
RuntimeError: ChatGoogleGenerativeAIError: Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-2.5-flash\nPlease retry in 4.01559499s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'model': 'gemini-2.5-flash', 'location': 'global'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '4s'}]}}
```
## 2026-06-02 21:28:15 JST

- Context: Unhandled Streamlit UI error
- Error Type: AttributeError
- Message: module 'app.config' has no attribute 'QWEN_MODEL'
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 525, in <module>
    main()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 513, in main
    render_qwen_rag_chat(force_rebuild)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 346, in render_qwen_rag_chat
    chatbot = load_qwen_chatbot(should_rebuild)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 280, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 325, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 384, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 53, in load_qwen_chatbot
    return QwenRAGChatbot(force_rebuild_index=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/qwen.py", line 38, in __init__
    self.llm = build_qwen_llm()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/qwen.py", line 21, in build_qwen_llm
    model=config.QWEN_MODEL,
AttributeError: module 'app.config' has no attribute 'QWEN_MODEL'
```
## 2026-06-02 21:27:38 JST

- Context: Unhandled Streamlit UI error
- Error Type: AttributeError
- Message: module 'app.config' has no attribute 'QWEN_MODEL'
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 525, in <module>
    main()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 513, in main
    render_qwen_rag_chat(force_rebuild)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 346, in render_qwen_rag_chat
    chatbot = load_qwen_chatbot(should_rebuild)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 280, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 325, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/streamlit/runtime/caching/cache_utils.py", line 384, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 53, in load_qwen_chatbot
    return QwenRAGChatbot(force_rebuild_index=force_rebuild_index)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/qwen.py", line 38, in __init__
    self.llm = build_qwen_llm()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/qwen.py", line 21, in build_qwen_llm
    model=config.QWEN_MODEL,
AttributeError: module 'app.config' has no attribute 'QWEN_MODEL'
```
## 2026-06-02 21:44:47 JST

- Context: Unhandled Streamlit UI error
- Error Type: ImportError
- Message: cannot import name 'ask_qwen' from 'app.qwen' (/Users/adachiitsuki/Desktop/recipe_chatbot/app/qwen.py)
- Python: 3.10.12

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 579, in <module>
    main()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 567, in main
    render_qwen_chat()
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 399, in render_qwen_chat
    from app.qwen import ask_qwen
ImportError: cannot import name 'ask_qwen' from 'app.qwen' (/Users/adachiitsuki/Desktop/recipe_chatbot/app/qwen.py)
```
## 2026-06-03 12:11:04 JST

- Context: Sidebar LangGraph Deep Agent collection
- Error Type: RuntimeError
- Message: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/categories/recipes/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/breakfast/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/lunch/: ValueError: Recipe text is too short to index safely (0 chars).
- Python: 3.10.12

### Details

```text
query=Omelet rice, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 159, in save_selected_pages
    saved_pages = save_many_recipe_pages(selected_urls, max_pages=state["max_pages"])
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 171, in save_many_recipe_pages
    raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
RuntimeError: No pages were saved.
https://www.justonecookbook.com/categories/recipes/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/breakfast/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/lunch/: ValueError: Recipe text is too short to index safely (0 chars).

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 227, in render_sidebar
    result = run_deep_agent_recipe_collection_with_details(
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 196, in run_deep_agent_recipe_collection_with_details
    state = graph.invoke(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 3068, in invoke
    for chunk in self.stream(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 2643, in stream
    for _ in runner.tick(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_runner.py", line 167, in tick
    run_with_retry(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_retry.py", line 42, in run_with_retry
    return task.proc.invoke(task.input, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 656, in invoke
    input = context.run(step.invoke, input, config, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 400, in invoke
    ret = self.func(*args, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 162, in save_selected_pages
    raise RuntimeError("Selected URLs could not be saved.\n" + "\n".join(errors[:5])) from exc
RuntimeError: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/categories/recipes/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/breakfast/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/lunch/: ValueError: Recipe text is too short to index safely (0 chars).
```
## 2026-06-03 12:13:40 JST

- Context: Sidebar LangGraph Deep Agent collection
- Error Type: ChatGoogleGenerativeAIError
- Message: Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-2.5-flash\nPlease retry in 19.668815343s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '19s'}]}}
- Python: 3.10.12

### Details

```text
query=Omurice, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_google_genai/chat_models.py", line 3194, in _generate
    response: GenerateContentResponse = self.client.models.generate_content(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/models.py", line 6454, in generate_content
    response = self._generate_content(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/models.py", line 4890, in _generate_content
    response = self._api_client.request(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/_api_client.py", line 1611, in request
    response = self._request(http_request, http_options, stream=False)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/_api_client.py", line 1402, in _request
    return retry(self._request_once, http_request, stream)  # type: ignore[no-any-return]
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/tenacity/__init__.py", line 477, in __call__
    do = self.iter(retry_state=retry_state)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/tenacity/__init__.py", line 378, in iter
    result = action(retry_state)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/tenacity/__init__.py", line 420, in exc_check
    raise retry_exc.reraise()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/tenacity/__init__.py", line 187, in reraise
    raise self.last_attempt.result()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/concurrent/futures/_base.py", line 451, in result
    return self.__get_result()
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/concurrent/futures/_base.py", line 403, in __get_result
    raise self._exception
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/tenacity/__init__.py", line 480, in __call__
    result = fn(*args, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/_api_client.py", line 1381, in _request_once
    errors.APIError.raise_for_response(response)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/errors.py", line 155, in raise_for_response
    cls.raise_error(response.status_code, response_json, response)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/google/genai/errors.py", line 184, in raise_error
    raise ClientError(status_code, response_json, response)
google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-2.5-flash\nPlease retry in 19.668815343s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '19s'}]}}

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 227, in render_sidebar
    result = run_deep_agent_recipe_collection_with_details(
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 196, in run_deep_agent_recipe_collection_with_details
    state = graph.invoke(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 3068, in invoke
    for chunk in self.stream(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 2643, in stream
    for _ in runner.tick(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_runner.py", line 167, in tick
    run_with_retry(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_retry.py", line 42, in run_with_retry
    return task.proc.invoke(task.input, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 656, in invoke
    input = context.run(step.invoke, input, config, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 400, in invoke
    ret = self.func(*args, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 126, in select_recipe_urls
    response = llm.invoke(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_google_genai/chat_models.py", line 2672, in invoke
    return super().invoke(input, config, stop=stop, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/chat_models.py", line 474, in invoke
    self.generate_prompt(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/chat_models.py", line 1823, in generate_prompt
    return self.generate(prompt_messages, stop=stop, callbacks=callbacks, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/chat_models.py", line 1630, in generate
    self._generate_with_cache(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_core/language_models/chat_models.py", line 1970, in _generate_with_cache
    result = self._generate(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_google_genai/chat_models.py", line 3198, in _generate
    _handle_client_error(e, request)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langchain_google_genai/chat_models.py", line 169, in _handle_client_error
    raise ChatGoogleGenerativeAIError(msg) from e
langchain_google_genai.chat_models.ChatGoogleGenerativeAIError: Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-2.5-flash\nPlease retry in 19.668815343s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '19s'}]}}
```
## 2026-06-03 21:18:19 JST

- Context: Sidebar LangGraph Deep Agent collection
- Error Type: RuntimeError
- Message: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/categories/recipes/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/lunch/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/breakfast/: ValueError: Recipe text is too short to index safely (0 chars).
- Python: 3.10.12

### Details

```text
query=Omurice, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 159, in save_selected_pages
    def build_recipe_collection_graph():
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 171, in save_many_recipe_pages
    raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
RuntimeError: No pages were saved.
https://www.justonecookbook.com/categories/recipes/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/lunch/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/breakfast/: ValueError: Recipe text is too short to index safely (0 chars).

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 238, in render_sidebar
    result = run_deep_agent_recipe_collection_with_details(
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 196, in run_deep_agent_recipe_collection_with_details
    "saved_pages": [],
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 3068, in invoke
    for chunk in self.stream(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 2643, in stream
    for _ in runner.tick(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_runner.py", line 167, in tick
    run_with_retry(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_retry.py", line 42, in run_with_retry
    return task.proc.invoke(task.input, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 656, in invoke
    input = context.run(step.invoke, input, config, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 400, in invoke
    ret = self.func(*args, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 162, in save_selected_pages
    from langgraph.graph import END, START, StateGraph
RuntimeError: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/categories/recipes/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/lunch/: ValueError: Recipe text is too short to index safely (0 chars).
https://www.justonecookbook.com/categories/recipes/breakfast/: ValueError: Recipe text is too short to index safely (0 chars).
```
## 2026-06-03 21:36:19 JST

- Context: Sidebar LangGraph Deep Agent collection
- Error Type: RuntimeError
- Message: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).
- Python: 3.10.12

### Details

```text
query=Omurice, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 152, in save_selected_pages
    saved_pages = save_many_recipe_pages(selected_urls, max_pages=state["max_pages"])
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 197, in save_many_recipe_pages
    raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 238, in render_sidebar
    result = run_deep_agent_recipe_collection_with_details(
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 189, in run_deep_agent_recipe_collection_with_details
    state = graph.invoke(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 3068, in invoke
    for chunk in self.stream(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 2643, in stream
    for _ in runner.tick(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_runner.py", line 167, in tick
    run_with_retry(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_retry.py", line 42, in run_with_retry
    return task.proc.invoke(task.input, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 656, in invoke
    input = context.run(step.invoke, input, config, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 400, in invoke
    ret = self.func(*args, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 155, in save_selected_pages
    raise RuntimeError("Selected URLs could not be saved.\n" + "\n".join(errors[:5])) from exc
RuntimeError: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).
```
## 2026-06-03 21:59:01 JST

- Context: Sidebar LangGraph Deep Agent collection
- Error Type: RuntimeError
- Message: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).
- Python: 3.10.12

### Details

```text
query=Omurice, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 152, in save_selected_pages
    saved_pages = save_many_recipe_pages(selected_urls, max_pages=state["max_pages"])
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 197, in save_many_recipe_pages
    raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 239, in render_sidebar
    result = run_deep_agent_recipe_collection_with_details(
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 189, in run_deep_agent_recipe_collection_with_details
    state = graph.invoke(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 3068, in invoke
    for chunk in self.stream(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 2643, in stream
    for _ in runner.tick(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_runner.py", line 167, in tick
    run_with_retry(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_retry.py", line 42, in run_with_retry
    return task.proc.invoke(task.input, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 656, in invoke
    input = context.run(step.invoke, input, config, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 400, in invoke
    ret = self.func(*args, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 155, in save_selected_pages
    raise RuntimeError("Selected URLs could not be saved.\n" + "\n".join(errors[:5])) from exc
RuntimeError: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).
```
## 2026-06-03 22:39:35 JST

- Context: Sidebar crawl4ai Agentic Crawler collection
- Error Type: RuntimeError
- Message: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).
- Python: 3.10.12

### Details

```text
query=Omurice, max_pages=3
```

### Traceback

```text
Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 152, in save_selected_pages
    urls.append(url)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/scraper.py", line 197, in save_many_recipe_pages
    raise RuntimeError("No pages were saved.\n" + "\n".join(errors[:5]))
RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app.py", line 244, in render_sidebar
    result = run_deep_agent_recipe_collection_with_details(
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 189, in run_deep_agent_recipe_collection_with_details
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 3068, in invoke
    for chunk in self.stream(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/main.py", line 2643, in stream
    for _ in runner.tick(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_runner.py", line 167, in tick
    run_with_retry(
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/pregel/_retry.py", line 42, in run_with_retry
    return task.proc.invoke(task.input, config)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 656, in invoke
    input = context.run(step.invoke, input, config, **kwargs)
  File "/Users/adachiitsuki/.pyenv/versions/3.10.12/lib/python3.10/site-packages/langgraph/_internal/_runnable.py", line 400, in invoke
    ret = self.func(*args, **kwargs)
  File "/Users/adachiitsuki/Desktop/recipe_chatbot/app/deep_agent.py", line 155, in save_selected_pages
    return urls
RuntimeError: Selected URLs could not be saved.
save_selected_pages: RuntimeError: No pages were saved.
https://www.justonecookbook.com/5-easy-japanese-dishes/: ValueError: Recipe text is too short to index safely (0 chars).
```
