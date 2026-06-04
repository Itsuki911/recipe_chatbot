# Adaptive Crawling Research Architecture

## Purpose

This architecture uses crawl4ai Adaptive Crawling to investigate a website from a starting URL, extract useful text, follow internal URLs, expand the investigation scope, and synthesize the findings with the configured LLM.

## Components

- `app/adaptive_crawler.py`: orchestration module for adaptive crawl execution, knowledge-base export, and LLM synthesis.
- `crawl4ai.AsyncWebCrawler`: browser-backed page loading and text extraction.
- `crawl4ai.AdaptiveCrawler`: query-driven crawl expansion across internal links.
- `crawl4ai.AdaptiveConfig`: confidence, depth, page, and link-follow controls.
- `app.llm.build_chat_llm`: Qwen by default, Gemini when configured.
- `data/adaptive_crawls/<run>/knowledge_base.jsonl`: exported crawl knowledge base.
- `data/adaptive_crawls/<run>/result.json`: metadata, relevant pages, architecture, timings, and synthesis.
- `app.py` `Adaptive Crawl`: Streamlit UI for running and inspecting investigations.

## Data Flow

1. User provides `start_url`, research `query`, and adaptive crawl limits.
2. `AdaptiveConfig` controls the crawl with:
   - `confidence_threshold`
   - `max_pages`
   - `max_depth`
   - `top_k_links`
   - `strategy` (`statistical` or `embedding`)
3. `AdaptiveCrawler.digest()` crawls from the seed URL, extracts text, ranks internal URLs, and follows links that add information gain for the query.
4. `AdaptiveCrawler.get_relevant_content()` selects the most relevant pages.
5. `AdaptiveCrawler.export_knowledge_base()` writes raw crawl knowledge to JSONL.
6. The configured LLM receives compact excerpts from relevant pages and produces:
   - findings
   - cited URLs
   - uncertainty and gaps
   - recommended next internal URLs or subtopics
7. The UI displays metrics, synthesis, relevant pages, crawled URLs, saved files, and the architecture object.

## LLM Usage

The crawler itself uses crawl4ai's adaptive ranking and confidence model to decide where to go next. The app then uses the configured chat LLM to reason over the collected evidence and produce a research synthesis.

Default:

```env
STRUCTURED_LLM_BACKEND=qwen
QWEN_BASE_URL=http://localhost:11434/v1
QWEN_MODEL=qwen3:4b
```

Gemini fallback:

```env
STRUCTURED_LLM_BACKEND=gemini
GOOGLE_API_KEY=...
```

## Verification

Local verification should include:

- `python -m compileall app/adaptive_crawler.py app.py`
- `python -c "from app.adaptive_crawler import adaptive_architecture_preview; print(adaptive_architecture_preview()['pipeline'][0])"`
- A small UI run with low limits, such as `max_pages=3`, `max_depth=1`, `top_k_links=1`.

The last check performs real web and LLM calls, so it requires network access and a working Qwen/Ollama or Gemini backend.
