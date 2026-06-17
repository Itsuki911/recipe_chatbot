from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config


@dataclass(frozen=True)
class GCSObject:
    name: str
    uri: str
    content_type: str | None = None


def is_enabled() -> bool:
    return bool(config.GCS_BUCKET)


def _client():
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("Install google-cloud-storage to use GCS_BUCKET storage.") from exc

    return storage.Client()


def _object_name(name: str) -> str:
    cleaned = name.strip().lstrip("/")
    if not config.GCS_PREFIX:
        return cleaned
    prefix = config.GCS_PREFIX.strip("/")
    if cleaned.startswith(f"{prefix}/"):
        return cleaned
    return f"{prefix}/{cleaned}"


def gcs_uri(name: str) -> str:
    return f"gs://{config.GCS_BUCKET}/{_object_name(name)}"


def upload_text(name: str, text: str, *, content_type: str = "text/plain; charset=utf-8") -> GCSObject:
    if not is_enabled():
        raise RuntimeError("GCS_BUCKET is not set.")
    object_name = _object_name(name)
    bucket = _client().bucket(config.GCS_BUCKET)
    blob = bucket.blob(object_name)
    blob.upload_from_string(text, content_type=content_type)
    return GCSObject(name=object_name, uri=f"gs://{config.GCS_BUCKET}/{object_name}", content_type=content_type)


def upload_json(name: str, payload: dict[str, Any]) -> GCSObject:
    return upload_text(
        name,
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        content_type="application/json; charset=utf-8",
    )


def download_text(name: str) -> str:
    if not is_enabled():
        raise RuntimeError("GCS_BUCKET is not set.")
    object_name = _object_name(name)
    bucket = _client().bucket(config.GCS_BUCKET)
    blob = bucket.blob(object_name)
    if not blob.exists():
        raise FileNotFoundError(gcs_uri(name))
    return blob.download_as_text(encoding="utf-8")


def download_json(name: str) -> dict[str, Any]:
    return json.loads(download_text(name))


def list_text_objects(prefix: str) -> list[GCSObject]:
    if not is_enabled():
        return []
    object_prefix = _object_name(prefix).rstrip("/") + "/"
    client = _client()
    objects: list[GCSObject] = []
    for blob in client.list_blobs(config.GCS_BUCKET, prefix=object_prefix):
        suffix = Path(blob.name).suffix.lower()
        if suffix not in {".html", ".htm", ".txt", ".md"}:
            continue
        objects.append(
            GCSObject(
                name=blob.name,
                uri=f"gs://{config.GCS_BUCKET}/{blob.name}",
                content_type=blob.content_type,
            )
        )
    return objects


def download_object_text(object_name: str) -> str:
    if not is_enabled():
        raise RuntimeError("GCS_BUCKET is not set.")
    bucket = _client().bucket(config.GCS_BUCKET)
    blob = bucket.blob(object_name)
    if not blob.exists():
        raise FileNotFoundError(f"gs://{config.GCS_BUCKET}/{object_name}")
    return blob.download_as_text(encoding="utf-8")
