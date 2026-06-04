from __future__ import annotations

import re
from hashlib import sha1
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import bs4
import requests
from langchain_core.documents import Document
from langchain_core.language_models.llms import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import PrivateAttr

from app.llm import build_chat_llm, strip_hidden_reasoning

try:
    from app import config as app_config
except ImportError:
    # 起動直後のimportエラー対策です。configが読めない場合でもfallback値で最低限動かします。
    app_config = None

# config.pyから値を読み込みます。getattrを使うことで、設定項目が一時的に欠けても落ちにくくしています。
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EMBEDDING_MODEL = getattr(app_config, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
FASTEMBED_MODEL = getattr(app_config, "FASTEMBED_MODEL", EMBEDDING_MODEL)
FASTEMBED_CACHE_DIR = getattr(app_config, "FASTEMBED_CACHE_DIR", DATA_DIR / "fastembed_cache")
EMBEDDING_DIMS = getattr(app_config, "EMBEDDING_DIMS", 384)
TURBOVEC_INDEX_DIR = getattr(app_config, "TURBOVEC_INDEX_DIR", DATA_DIR / "turbovec_index")
VECTOR_INDEX_DIR = getattr(app_config, "VECTOR_INDEX_DIR", TURBOVEC_INDEX_DIR)
HF_MODEL_ID = getattr(app_config, "HF_MODEL_ID", "google/gemma-4-E2B-it")
JOC_MAX_PAGES = getattr(app_config, "JOC_MAX_PAGES", 12)
JOC_RECIPE_URLS = getattr(
    app_config,
    "JOC_RECIPE_URLS",
    [
        "https://www.justonecookbook.com/tamagoyaki-japanese-rolled-omelette/",
        "https://www.justonecookbook.com/tonjiru/",
        "https://www.justonecookbook.com/miso-soup/",
        "https://www.justonecookbook.com/dashi/",
    ],
)
JOC_START_URL = getattr(app_config, "JOC_START_URL", "https://www.justonecookbook.com/")
LOCAL_RECIPE_DIR = getattr(app_config, "LOCAL_RECIPE_DIR", DATA_DIR / "joc_pages")
WEB_RECIPE_REFERENCE_DIR = getattr(app_config, "WEB_RECIPE_REFERENCE_DIR", DATA_DIR / "web_recipe_reference")
GOOGLE_API_KEY = getattr(app_config, "GOOGLE_API_KEY", None)
GEMINI_MODEL = getattr(app_config, "GEMINI_MODEL", "gemini-2.5-flash")
RAG_LLM_BACKEND = getattr(app_config, "RAG_LLM_BACKEND", "qwen")
RAG_EMBEDDING_BACKEND = getattr(app_config, "RAG_EMBEDDING_BACKEND", "fastembed")
RAG_VECTOR_STORE = getattr(app_config, "RAG_VECTOR_STORE", "turbovec")
TURBOVEC_BIT_WIDTH = getattr(app_config, "TURBOVEC_BIT_WIDTH", 4)


@dataclass
class RAGResponse:
    # UI側に返す回答本文と、回答の根拠になったsource一覧をまとめます。
    answer: str
    sources: list[str]


class LocalHuggingFaceRecipeLLM(LLM):
    """Small LangChain wrapper that supports the Gemma image-text model used in the notebook."""

    model_id: str = HF_MODEL_ID
    max_new_tokens: int = 900
    temperature: float = 0.1
    top_p: float = 0.9
    _model: object = PrivateAttr(default=None)
    _processor: object = PrivateAttr(default=None)
    _tokenizer: object = PrivateAttr(default=None)
    _mode: str = PrivateAttr(default="image_text")

    @property
    def _llm_type(self) -> str:
        return "local_huggingface_recipe_llm"

    def _load(self) -> None:
        if self._model is not None:
            return
        # transformersは重い依存なので、ローカルHugging Face backendを使う時だけimportします。
        try:
            from transformers import (
                AutoModelForCausalLM,
                AutoModelForImageTextToText,
                AutoProcessor,
                AutoTokenizer,
            )
        except ImportError as exc:
            raise RuntimeError(
                "Local Hugging Face backend is not installed. "
                "Use RAG_LLM_BACKEND=qwen with Ollama, RAG_LLM_BACKEND=gemini with GOOGLE_API_KEY, "
                "or install the full requirements.txt."
            ) from exc

        try:
            import accelerate  # noqa: F401
        except ImportError as exc:
            # accelerateがない環境ではdevice_map="auto"を使えないため、CPU寄りの読み込みにします。
            accelerate_error = exc
            model_load_kwargs = {}
        else:
            accelerate_error = None
            model_load_kwargs = {"device_map": "auto"}

        try:
            # Gemmaのimage-text系モデルとして読み込める場合はこちらを優先します。
            self._processor = AutoProcessor.from_pretrained(self.model_id, padding_side="left")
            self._model = AutoModelForImageTextToText.from_pretrained(
                self.model_id,
                attn_implementation="sdpa",
                **model_load_kwargs,
            )
            self._mode = "image_text"
            return
        except Exception as image_text_exc:
            try:
                # image-textとして読めないモデルでも、通常のcausal LMとして読める可能性があります。
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                self._model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_load_kwargs)
                self._mode = "causal"
                return
            except Exception as causal_exc:
                accelerate_note = (
                    " `accelerate` is not installed, so the fallback tried loading without "
                    '`device_map="auto"`.'
                    if accelerate_error
                    else ""
                )
                raise RuntimeError(
                    f"Failed to load local Hugging Face model `{self.model_id}`."
                    f"{accelerate_note} Set GOOGLE_API_KEY in .env to use Gemini, "
                    "or use the Docker environment documented in README.md."
                ) from causal_exc

    def _call(self, prompt: str, stop: list[str] | None = None, **kwargs) -> str:
        self._load()
        if self._mode == "image_text":
            # image-textモデルはchat templateを通して、会話形式の入力に変換します。
            messages = [{"role": "user", "content": prompt}]
            inputs = self._processor.apply_chat_template(
                messages,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                add_generation_prompt=True,
            ).to(self._model.device)
            input_len = inputs["input_ids"].shape[-1]
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            text = self._processor.decode(output[0][input_len:], skip_special_tokens=True)
        else:
            # causal LMの場合はtokenizerで直接プロンプトをtokenizeします。
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
            input_len = inputs["input_ids"].shape[-1]
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            text = self._tokenizer.decode(output[0][input_len:], skip_special_tokens=True)
        if stop:
            # LangChainからstop tokenが渡された場合は、それ以降の文字を切り落とします。
            for token in stop:
                text = text.split(token)[0]
        return text.strip()


def _headers() -> dict[str, str]:
    # Just One Cookbookにアクセスする時のHTTPヘッダーです。
    # ブラウザに近いUser-Agentを付けると、単純なbot判定を避けやすくなります。
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
    }


def discover_recipe_urls(start_url: str = JOC_START_URL, max_pages: int = JOC_MAX_PAGES) -> list[str]:
    """Collect a small, respectful set of same-site recipe URLs from Just One Cookbook."""
    try:
        response = requests.get(start_url, headers=_headers(), timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        # Web取得が失敗した場合は、設定済みの代表URLを使います。
        return JOC_RECIPE_URLS[:max_pages]
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        # 相対URLを絶対URLに変換し、同じサイト内のリンクだけを候補にします。
        href = urljoin(start_url, anchor["href"]).split("#")[0]
        parsed = urlparse(href)
        if parsed.netloc != urlparse(start_url).netloc:
            continue
        if not re.search(r"/(recipes|[a-z0-9-]+/)$", parsed.path):
            continue
        if href in seen:
            continue
        # 同じURLを重複登録しないようにseenで管理します。
        seen.add(href)
        urls.append(href)
        if len(urls) >= max_pages:
            break
    fallback_urls = [url for url in JOC_RECIPE_URLS if url not in seen]
    return (urls + fallback_urls)[:max_pages] or [start_url]


def load_web_page(url: str) -> Document:
    # レシピ本文に関係しやすいHTML領域だけをBeautifulSoupで抽出します。
    strainer = bs4.SoupStrainer(class_=("entry-title", "entry-content", "wprm-recipe-container"))
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, "html.parser", parse_only=strainer)
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    return Document(page_content=text, metadata={"source": url})


def load_local_recipe_docs(local_dir: Path = LOCAL_RECIPE_DIR) -> list[Document]:
    # 自動スクレイピングが403になる場合に備え、ブラウザ保存したローカルファイルを優先します。
    docs: list[Document] = []
    if not local_dir.exists():
        return docs
    for path in sorted(local_dir.glob("*")):
        if path.suffix.lower() not in {".html", ".htm", ".txt", ".md"}:
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() in {".html", ".htm"}:
            # HTMLはタグを除去して、検索用の素のテキストにします。
            soup = bs4.BeautifulSoup(raw, "html.parser")
            text = soup.get_text("\n", strip=True)
        else:
            text = raw
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > 500:
            # 短すぎるファイルはレシピ本文ではない可能性が高いため除外します。
            docs.append(Document(page_content=text, metadata={"source": f"local:{local_dir.name}/{path.name}"}))
    return docs


def load_reference_recipe_docs() -> list[Document]:
    docs: list[Document] = []
    for directory in (LOCAL_RECIPE_DIR, WEB_RECIPE_REFERENCE_DIR):
        docs.extend(load_local_recipe_docs(directory))
    return docs


def load_just_one_cookbook_docs(urls: Iterable[str] | None = None) -> list[Document]:
    # まずローカル保存済み文書を使います。Deep Agentのweb_recipe_referenceもRAG対象です。
    docs: list[Document] = load_reference_recipe_docs()
    if docs:
        return docs

    reference_dirs = (LOCAL_RECIPE_DIR, WEB_RECIPE_REFERENCE_DIR)
    local_files = []
    for directory in reference_dirs:
        if directory.exists():
            local_files.extend(
                str(path)
                for path in sorted(directory.glob("*"))
                if path.is_file() and path.name != ".gitkeep"
            )
    failures: list[str] = [
        # 失敗時のエラーメッセージに、調査しやすい情報を残します。
        f"Local recipe docs loaded: 0 from {', '.join(str(path) for path in reference_dirs)}",
        f"Local recipe files found: {len(local_files)}",
    ]
    for url in urls or discover_recipe_urls():
        try:
            doc = load_web_page(url)
        except requests.RequestException as exc:
            failures.append(f"{url}: {type(exc).__name__}: {exc}")
            continue
        if len(doc.page_content) > 500:
            docs.append(doc)
        else:
            failures.append(f"{url}: page loaded but recipe text was too short ({len(doc.page_content)} chars)")
    if not docs:
        detail = "\n".join(failures[:5]) or "No URLs were discovered."
        raise RuntimeError(
            "No recipe documents could be loaded from local reference folders or Just One Cookbook.\n"
            "The source site may be returning 403 to automated Python requests. "
            "Save recipe pages as .html/.txt/.md under data/joc_pages or data/web_recipe_reference, "
            "then rebuild the index.\n"
            f"Failures:\n{detail}"
        )
    return docs


def get_embeddings():
    # embeddingは文章をベクトルに変換する部品です。RAG検索の土台になります。
    if RAG_EMBEDDING_BACKEND in {"fastembed", "auto"}:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

        return FastEmbedEmbeddings(
            model_name=FASTEMBED_MODEL,
            cache_dir=str(FASTEMBED_CACHE_DIR),
        )

    if RAG_EMBEDDING_BACKEND == "gemini":
        # Gemini embeddingを選んだ場合はAPIキーが必要です。
        if not GOOGLE_API_KEY:
            raise RuntimeError(
                "Gemini embeddings are selected, but GOOGLE_API_KEY is not set. "
                "This project defaults to free local FastEmbed embeddings; use RAG_EMBEDDING_BACKEND=fastembed."
            )
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=GOOGLE_API_KEY)

    try:
        # 互換用のHugging Face embedding backendです。Dockerでは通常使いません。
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "Hugging Face embeddings are not installed in this environment. "
            "Docker mode uses free local FastEmbed embeddings; use RAG_EMBEDDING_BACKEND=fastembed."
        ) from exc

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def _stable_doc_id(doc: Document, index: int) -> str:
    # 同じ文書から同じIDを作ることで、index再構築時の追跡をしやすくします。
    source = doc.metadata.get("source", "")
    start = doc.metadata.get("start_index", index)
    digest = sha1(f"{source}:{start}:{doc.page_content[:120]}".encode("utf-8")).hexdigest()
    return digest


def _with_stable_ids(docs: list[Document]) -> list[Document]:
    return [
        Document(id=_stable_doc_id(doc, index), page_content=doc.page_content, metadata=doc.metadata)
        for index, doc in enumerate(docs)
    ]


def build_or_load_vector_store(
    index_dir: Path = VECTOR_INDEX_DIR,
    force_rebuild: bool = False,
):
    # 既存のTurboVec indexがあれば読み込み、なければレシピ文書から作ります。
    embeddings = get_embeddings()
    if RAG_VECTOR_STORE != "turbovec":
        raise RuntimeError("This project is configured to use TurboVec. Set RAG_VECTOR_STORE=turbovec.")

    if index_dir.exists() and not force_rebuild:
        from turbovec.langchain import TurboQuantVectorStore

        return TurboQuantVectorStore.load(str(index_dir), embedding=embeddings)

    docs = load_just_one_cookbook_docs()
    # 長いレシピ文書を1000文字ごとのチャンクに分けます。
    # overlapにより、境界付近の文脈が検索時に失われにくくなります。
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True,
    )
    splits = _with_stable_ids(splitter.split_documents(docs))
    from turbovec.langchain import TurboQuantVectorStore

    vector_store = TurboQuantVectorStore(embeddings, bit_width=TURBOVEC_BIT_WIDTH)
    # 分割済みチャンクをベクトル化してTurboVecに登録します。
    vector_store.add_documents(splits)
    index_dir.mkdir(parents=True, exist_ok=True)
    vector_store.dump(str(index_dir))
    return vector_store


def build_llm(llm_backend: str | None = None):
    # 回答生成モデルを選びます。デフォルトはQwenです。Geminiは明示選択時に使えます。
    selected_backend = (llm_backend or RAG_LLM_BACKEND or "qwen").lower()
    if selected_backend in {"qwen", "ollama", "gemini", "google"}:
        return build_chat_llm(selected_backend, temperature=0.1)

    return LocalHuggingFaceRecipeLLM(model_id=HF_MODEL_ID)


def format_docs(docs: list[Document]) -> str:
    # retrieverが返したDocumentを、LLMに渡しやすいテキスト形式に整えます。
    return "\n\n".join(
        f"Source: {doc.metadata.get('source')}\nContent:\n{doc.page_content}" for doc in docs
    )


class RecipeRAGChatbot:
    def __init__(self, force_rebuild_index: bool = False, llm_backend: str | None = None) -> None:
        # RAGの3要素: vector_store(検索DB), retriever(検索器), llm(回答生成モデル)を準備します。
        self.vector_store = build_or_load_vector_store(force_rebuild=force_rebuild_index)
        # k=4なので、質問ごとに関連度の高いチャンクを最大4件取得します。
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 4})
        self.llm = build_llm(llm_backend=llm_backend)
        from app.memory import RecipeLongTermMemory

        self.memory = RecipeLongTermMemory()
        # system promptで「取得したレシピ参照文脈だけを使う」ように強く指定します。
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a recipe inference assistant specializing in Japanese home cooking.
Use only the retrieved recipe reference context below. If the context is insufficient,
say that the recipe database does not contain enough information.

Rules:
- Do not mix up recipes with similar names.
- Include ingredients, clear steps, and practical cooking notes.
- Explain relevant differences from similar Japanese dishes when useful.
- Mention source URLs briefly at the end.
- Answer in the same language as the user's question unless they ask otherwise.
- Use the user's long-term memory only for preferences, dietary constraints, and continuity.

Long-term user memory:
{memory}

Context:
{context}""",
                ),
                ("human", "{question}"),
            ]
        )
        self.chain = (prompt | self.llm | StrOutputParser()).with_retry(
            # LLMやネットワークの一時的な失敗に備えて、最大3回まで再試行します。
            stop_after_attempt=3,
            wait_exponential_jitter=True,
        )

    def answer(self, question: str, user_id: str | None = None) -> RAGResponse:
        # 1. 質問に近いレシピチャンクを検索します。
        docs = self.retriever.invoke(question)
        # 2. 過去の会話から、好みや制約に関係するメモリを検索します。
        memory = self.memory.search(question, user_id=user_id)
        # 3. RAG文脈 + メモリ + 質問をLLMへ渡して回答を生成します。
        answer = self.chain.invoke(
            {
                "context": format_docs(docs),
                "memory": memory or "No relevant user memory found.",
                "question": question,
            }
        )
        answer = strip_hidden_reasoning(str(answer))
        # 4. 今回のやり取りを長期メモリへ保存します。
        self.memory.add_interaction(question, answer, user_id=user_id)
        # 5. UIで根拠を表示できるようにsource一覧を返します。
        sources = sorted({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})
        return RAGResponse(answer=answer, sources=sources)
