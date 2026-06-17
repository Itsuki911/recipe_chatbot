from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from app import config
from app.deep_agent import run_deep_agent_recipe_collection_with_details


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_request(request_object: str | None) -> dict[str, Any]:
    if not request_object:
        return {}
    from app.gcs_storage import download_json

    return download_json(request_object.removeprefix(f"gs://{config.GCS_BUCKET}/"))


def _write_status(request_id: str, payload: dict[str, Any]) -> None:
    if not config.GCS_BUCKET:
        return
    from app.gcs_storage import upload_json

    upload_json(f"results/{request_id}/status.json", {"updated_at": _now(), **payload})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Deep Agent recipe collection as a Cloud Run Job.")
    parser.add_argument("--query", default=os.getenv("DEEP_AGENT_QUERY", ""))
    parser.add_argument("--max-pages", type=int, default=int(os.getenv("DEEP_AGENT_MAX_PAGES", "3")))
    parser.add_argument("--request-object", default=os.getenv("REQUEST_OBJECT", ""))
    args = parser.parse_args(argv)

    request_payload = _load_request(args.request_object or None)
    query = str(request_payload.get("query") or args.query).strip()
    max_pages = int(request_payload.get("max_pages") or args.max_pages)
    request_id = str(request_payload.get("request_id") or os.getenv("REQUEST_ID") or uuid.uuid4())

    if not query:
        raise ValueError("Deep Agent query is required. Set --query, DEEP_AGENT_QUERY, or REQUEST_OBJECT.")

    _write_status(
        request_id,
        {
            "status": "running",
            "query": query,
            "max_pages": max_pages,
            "request_id": request_id,
        },
    )
    try:
        result = run_deep_agent_recipe_collection_with_details(query, max_pages=max_pages)
    except Exception as exc:
        try:
            from app.error_logger import log_error

            log_error(
                "Deep Agent Cloud Run Job",
                exc,
                details=f"request_id={request_id}, query={query}, max_pages={max_pages}",
            )
        except Exception:
            pass
        _write_status(
            request_id,
            {
                "status": "failed",
                "query": query,
                "max_pages": max_pages,
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise

    saved_pages = [
        {
            "url": page.url,
            "local_path": str(page.path),
            "title": page.title,
            "text_chars": page.text_chars,
        }
        for page in result.saved_pages
    ]
    _write_status(
        request_id,
        {
            "status": "succeeded",
            "query": result.query,
            "max_pages": max_pages,
            "request_id": request_id,
            "search_queries": result.search_queries,
            "candidate_urls": result.candidate_urls,
            "selected_urls": result.selected_urls,
            "saved_pages": saved_pages,
            "notes": result.notes,
        },
    )
    print(f"Deep Agent job succeeded: request_id={request_id}, saved_pages={len(saved_pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
