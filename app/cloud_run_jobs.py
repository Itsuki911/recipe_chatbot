from __future__ import annotations

from typing import Any

import requests
from google.auth import default
from google.auth.transport.requests import Request

from app import config


def run_deep_agent_job(*, request_object: str, query: str, max_pages: int) -> dict[str, Any]:
    if not config.CLOUD_RUN_PROJECT_ID:
        raise RuntimeError("CLOUD_RUN_PROJECT_ID is not set.")
    if not config.CLOUD_RUN_DEEP_AGENT_JOB:
        raise RuntimeError("CLOUD_RUN_DEEP_AGENT_JOB is not set.")

    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    endpoint = (
        "https://run.googleapis.com/v2/"
        f"projects/{config.CLOUD_RUN_PROJECT_ID}/locations/{config.CLOUD_RUN_REGION}"
        f"/jobs/{config.CLOUD_RUN_DEEP_AGENT_JOB}:run"
    )
    payload = {
        "overrides": {
            "containerOverrides": [
                {
                    "env": [
                        {"name": "REQUEST_OBJECT", "value": request_object},
                        {"name": "DEEP_AGENT_QUERY", "value": query},
                        {"name": "DEEP_AGENT_MAX_PAGES", "value": str(max_pages)},
                    ]
                }
            ]
        }
    }
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
