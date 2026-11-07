"""Supabase access for the NutriBuddy API.

Requests use the anon key plus the signed-in parent's access token, so row-level
security stays in effect. The service-role key is never read here.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any
from uuid import UUID

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

logger = logging.getLogger("nutribuddy.database")

CHILD_COLUMNS = "id,parent_id,nickname,age,created_at"


class DatabaseError(Exception):
    """A database call failed. The message is for logs, not for the client."""

    def __init__(self, status_code: int, code: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(f"Database request failed ({status_code}, {code})")


class Settings(BaseModel):
    supabase_url: str
    supabase_key: str


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key or url.startswith("your_") or key.startswith("your_"):
        raise DatabaseError(503, "config")
    return Settings(supabase_url=url, supabase_key=key)


def request_json(
    method: str,
    path: str,
    token: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    prefer_representation: bool = False,
) -> Any:
    settings = get_settings()
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if prefer_representation:
        headers["Prefer"] = "return=representation"

    try:
        response = httpx.request(
            method,
            f"{settings.supabase_url}{path}",
            headers=headers,
            params=params,
            json=body,
            timeout=20.0,
        )
    except httpx.HTTPError:
        logger.warning("Supabase request could not connect method=%s path=%s", method, path)
        raise DatabaseError(503, "network") from None

    if response.status_code >= 400:
        code = _error_code(response)
        logger.warning(
            "Supabase request failed method=%s path=%s status=%s code=%s",
            method,
            path,
            response.status_code,
            code,
        )
        raise DatabaseError(response.status_code, code)

    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def create_child_record(token: str, parent_id: UUID, nickname: str, age: int) -> dict[str, Any]:
    payload = request_json(
        "POST",
        "/rest/v1/children",
        token,
        body={"parent_id": str(parent_id), "nickname": nickname, "age": age},
        prefer_representation=True,
    )
    row = _first_row(payload)
    if row is None:
        raise DatabaseError(502, "empty")
    return row


def list_child_records(token: str) -> list[dict[str, Any]]:
    payload = request_json(
        "GET",
        "/rest/v1/children",
        token,
        params={"select": CHILD_COLUMNS, "order": "created_at.desc"},
    )
    if not isinstance(payload, list):
        raise DatabaseError(502, "invalid_response")
    return payload


def get_child_record(token: str, child_id: UUID) -> dict[str, Any] | None:
    payload = request_json(
        "GET",
        "/rest/v1/children",
        token,
        params={"select": CHILD_COLUMNS, "id": f"eq.{child_id}"},
    )
    if not isinstance(payload, list):
        raise DatabaseError(502, "invalid_response")
    return _first_row(payload)


def _first_row(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        row = payload[0] if payload else None
    else:
        row = payload
    if not isinstance(row, dict):
        return None
    return row


def insert_chat_message(token: str, child_id: UUID, role: str, message: str) -> dict[str, Any]:
    payload = request_json(
        "POST",
        "/rest/v1/chat_messages",
        token,
        body={"child_id": str(child_id), "role": role, "message": message},
        prefer_representation=True,
    )
    row = _first_row(payload)
    if row is None:
        raise DatabaseError(502, "empty")
    return row


def list_chat_messages(token: str, child_id: UUID) -> list[dict[str, Any]]:
    payload = request_json(
        "GET",
        "/rest/v1/chat_messages",
        token,
        params={
            "select": "id,child_id,role,message,created_at",
            "child_id": f"eq.{child_id}",
            "order": "created_at.asc",
        },
    )
    if not isinstance(payload, list):
        raise DatabaseError(502, "invalid_response")
    return payload


def insert_quiz_attempt(
    token: str,
    child_id: UUID,
    topic: str,
    score: int,
    total_questions: int,
) -> dict[str, Any]:
    payload = request_json(
        "POST",
        "/rest/v1/quiz_attempts",
        token,
        body={
            "child_id": str(child_id),
            "topic": topic,
            "score": score,
            "total_questions": total_questions,
        },
        prefer_representation=True,
    )
    row = _first_row(payload)
    if row is None:
        raise DatabaseError(502, "empty")
    return row


def list_quiz_attempts(token: str, child_id: UUID) -> list[dict[str, Any]]:
    payload = request_json(
        "GET",
        "/rest/v1/quiz_attempts",
        token,
        params={
            "select": "id,child_id,topic,score,total_questions,created_at",
            "child_id": f"eq.{child_id}",
            "order": "created_at.asc",
        },
    )
    if not isinstance(payload, list):
        raise DatabaseError(502, "invalid_response")
    return payload


def _error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "error"
    if not isinstance(payload, dict):
        return "error"
    code = payload.get("code") or payload.get("error_code") or "error"
    return str(code)
