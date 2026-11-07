"""Calls the NutriBuddy FastAPI backend. Secrets stay on the server."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NutriBuddyClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("BACKEND_URL", "http://localhost:8000")).rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def register(self, name: str, email: str, password: str, consent: bool) -> dict[str, Any]:
        return self._request(
            "POST",
            "/auth/register",
            json={"name": name, "email": email, "password": password, "consent": consent},
        )

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request("POST", "/auth/login", json={"email": email, "password": password})

    def list_children(self, token: str) -> list[dict[str, Any]]:
        return self._request("GET", "/children", token=token)

    def create_child(self, token: str, nickname: str, age: int) -> dict[str, Any]:
        return self._request("POST", "/children", token=token, json={"nickname": nickname, "age": age})

    def chat_history(self, token: str, child_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/chat/history/{child_id}", token=token)

    def chat(self, token: str, child_id: str, message: str) -> dict[str, Any]:
        return self._request("POST", "/chat", token=token, json={"child_id": child_id, "message": message})

    def quiz_topics(self, token: str) -> list[str]:
        return self._request("GET", "/quiz/topics", token=token)

    def start_quiz(self, token: str, child_id: str, topic: str) -> dict[str, Any]:
        return self._request("GET", "/quiz", token=token, params={"child_id": child_id, "topic": topic})

    def check_answer(self, token: str, child_id: str, question_id: str, selected_index: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/quiz/answer",
            token=token,
            json={"child_id": child_id, "question_id": question_id, "selected_index": selected_index},
        )

    def submit_quiz(self, token: str, child_id: str, topic: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/quiz/submit",
            token=token,
            json={"child_id": child_id, "topic": topic, "answers": answers},
        )

    def progress(self, token: str, child_id: str) -> dict[str, Any]:
        return self._request("GET", f"/progress/{child_id}", token=token)

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=json,
                params=params,
                timeout=40.0,
            )
        except httpx.HTTPError as exc:
            raise ApiError(0, "The NutriBuddy server is not running. Start the API, then refresh this page.") from exc
        if response.status_code >= 400:
            raise ApiError(response.status_code, _detail(response))
        if not response.content:
            return None
        return response.json()


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Something went wrong. Please try again."
    detail = payload.get("detail", "Something went wrong. Please try again.")
    if isinstance(detail, list):
        messages = [str(item.get("msg", "Check the form and try again.")) for item in detail if isinstance(item, dict)]
        return " ".join(messages) or "Check the form and try again."
    return str(detail)
