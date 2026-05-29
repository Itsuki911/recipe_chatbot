from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import bs4
import requests
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.language_models.llms import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import PrivateAttr
from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor, AutoTokenizer

from app.config import (
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    HF_MODEL_ID,
    JOC_MAX_PAGES,
    JOC_RECIPE_URLS,
    JOC_START_URL,
    LOCAL_RECIPE_DIR,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


@dataclass
class RAGResponse:
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
        try:
            self._processor = AutoProcessor.from_pretrained(self.model_id, padding_side="left")
            self._model = AutoModelForImageTextToText.from_pretrained(
                self.model_id,
                device_map="auto",
                attn_implementation="sdpa",
            )
            self._mode = "image_text"
        except Exception:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._model = AutoModelForCausalLM.from_pretrained(self.model_id, device_map="auto")
            self._mode = "causal"

    def _call(self, prompt: str, stop: list[str] | None = None, **kwargs) -> str:
        self._load()
        if self._mode == "image_text":
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
            for token in stop:
                text = text.split(token)[0]
        return text.strip()


def _headers() -> dict[str, str]:
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
        return JOC_RECIPE_URLS[:max_pages]
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(start_url, anchor["href"]).split("#")[0]
        parsed = urlparse(href)
        if parsed.netloc != urlparse(start_url).netloc:
            continue
        if not re.search(r"/(recipes|[a-z0-9-]+/)$", parsed.path):
            continue
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
        if len(urls) >= max_pages:
            break
    fallback_urls = [url for url in JOC_RECIPE_URLS if url not in seen]
    return (urls + fallback_urls)[:max_pages] or [start_url]


def load_web_page(url: str) -> Document:
    strainer = bs4.SoupStrainer(class_=("entry-title", "entry-content", "wprm-recipe-container"))
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, "html.parser", parse_only=strainer)
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    return Document(page_content=text, metadata={"source": url})


def load_local_recipe_docs(local_dir: Path = LOCAL_RECIPE_DIR) -> list[Document]:
    docs: list[Document] = []
    if not local_dir.exists():
        return docs
    for path in sorted(local_dir.glob("*")):
        if path.suffix.lower() not in {".html", ".htm", ".txt", ".md"}:
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() in {".html", ".htm"}:
            soup = bs4.BeautifulSoup(raw, "html.parser")
            text = soup.get_text("\n", strip=True)
        else:
            text = raw
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > 500:
            docs.append(Document(page_content=text, metadata={"source": f"local:{path.name}"}))
    return docs


def load_just_one_cookbook_docs(urls: Iterable[str] | None = None) -> list[Document]:
    docs: list[Document] = load_local_recipe_docs()
    if docs:
        return docs

    failures: list[str] = []
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
            "No recipe documents could be loaded from Just One Cookbook.\n"
            "The site may be returning 403 to automated Python requests. "
            "Save recipe pages as .html/.txt/.md under data/joc_pages, then rebuild the index.\n"
            f"Failures:\n{detail}"
        )
    return docs


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def build_or_load_vector_store(
    index_dir: Path = FAISS_INDEX_DIR,
    force_rebuild: bool = False,
) -> FAISS:
    embeddings = get_embeddings()
    if index_dir.exists() and not force_rebuild:
        return FAISS.load_local(
            str(index_dir),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    docs = load_just_one_cookbook_docs()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True,
    )
    splits = splitter.split_documents(docs)
    vector_store = FAISS.from_documents(splits, embeddings)
    index_dir.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(index_dir))
    return vector_store


def build_llm():
    if OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=OPENAI_MODEL, temperature=0.1)

    return LocalHuggingFaceRecipeLLM(model_id=HF_MODEL_ID)


def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(
        f"Source: {doc.metadata.get('source')}\nContent:\n{doc.page_content}" for doc in docs
    )


class RecipeRAGChatbot:
    def __init__(self, force_rebuild_index: bool = False) -> None:
        self.vector_store = build_or_load_vector_store(force_rebuild=force_rebuild_index)
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 4})
        self.llm = build_llm()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a recipe inference assistant specializing in Japanese home cooking.
Use only the retrieved Just One Cookbook context below. If the context is insufficient,
say that the recipe database does not contain enough information.

Rules:
- Do not mix up recipes with similar names.
- Include ingredients, clear steps, and practical cooking notes.
- Explain relevant differences from similar Japanese dishes when useful.
- Mention source URLs briefly at the end.
- Answer in the same language as the user's question unless they ask otherwise.

Context:
{context}""",
                ),
                ("human", "{question}"),
            ]
        )
        self.chain = (
            {
                "context": self.retriever | format_docs,
                "question": RunnablePassthrough(),
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )

    def answer(self, question: str) -> RAGResponse:
        docs = self.retriever.invoke(question)
        answer = self.chain.invoke(question)
        sources = sorted({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})
        return RAGResponse(answer=answer, sources=sources)
