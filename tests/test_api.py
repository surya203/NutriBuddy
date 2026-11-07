"""Tests for the Phase 2 NutriBuddy API."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.auth import AuthenticatedParent, get_current_parent
from backend.database import DatabaseError
from backend.main import app

client = TestClient(app)
PARENT_ID = uuid4()


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _sign_in() -> AuthenticatedParent:
    parent = AuthenticatedParent(PARENT_ID, "parent@example.com", "test-token")
    app.dependency_overrides[get_current_parent] = lambda: parent
    return parent


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "nutribuddy"}


def test_children_require_a_token() -> None:
    response = client.get("/children")
    assert response.status_code == 401


def test_invalid_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.auth.fetch_parent", lambda token: None)
    response = client.get("/children", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_create_child_rejects_an_age_outside_the_range() -> None:
    _sign_in()
    response = client.post("/children", json={"nickname": "Ava", "age": 12})
    assert response.status_code == 422


def test_create_child_uses_the_signed_in_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _sign_in()
    child_id = uuid4()

    def fake_create(token: str, parent_id: object, nickname: str, age: int) -> dict[str, object]:
        assert token == "test-token"
        assert parent_id == parent.id
        return {
            "id": str(child_id),
            "parent_id": str(parent.id),
            "nickname": nickname,
            "age": age,
            "created_at": "2026-11-07T12:00:00+00:00",
        }

    monkeypatch.setattr("backend.main.create_child_record", fake_create)
    response = client.post("/children", json={"nickname": "  Ava  ", "age": 8})
    assert response.status_code == 201
    body = response.json()
    assert body["nickname"] == "Ava"
    assert body["parent_id"] == str(parent.id)
    assert body["age"] == 8


def test_list_children_hides_other_parents(monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _sign_in()
    monkeypatch.setattr(
        "backend.main.list_child_records",
        lambda token: [
            {
                "id": str(uuid4()),
                "parent_id": str(parent.id),
                "nickname": "Ava",
                "age": 8,
                "created_at": "2026-11-07T12:00:00+00:00",
            },
            {
                "id": str(uuid4()),
                "parent_id": str(uuid4()),
                "nickname": "Other",
                "age": 7,
                "created_at": "2026-11-07T12:00:00+00:00",
            },
        ],
    )
    response = client.get("/children")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["nickname"] == "Ava"


def test_missing_child_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _sign_in()
    monkeypatch.setattr("backend.main.get_child_record", lambda token, child_id: None)
    response = client.get(f"/children/{uuid4()}")
    assert response.status_code == 404


def test_missing_parent_profile_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    _sign_in()

    def fake_create(token: str, parent_id: object, nickname: str, age: int) -> dict[str, object]:
        raise DatabaseError(409, "23503")

    monkeypatch.setattr("backend.main.create_child_record", fake_create)
    response = client.post("/children", json={"nickname": "Ava", "age": 8})
    assert response.status_code == 409


def _child_row(child_id: object) -> dict[str, object]:
    return {
        "id": str(child_id),
        "parent_id": str(PARENT_ID),
        "nickname": "Ava",
        "age": 8,
        "created_at": "2026-11-07T12:00:00+00:00",
    }


def test_quiz_questions_do_not_include_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    _sign_in()
    child_id = uuid4()
    monkeypatch.setattr("backend.main.get_child_record", lambda token, requested_id: _child_row(requested_id))
    monkeypatch.setattr("backend.main.list_quiz_attempts", lambda token, requested_id: [])
    response = client.get("/quiz", params={"child_id": str(child_id), "topic": "Hydration"})
    assert response.status_code == 200
    question = response.json()["questions"][0]
    assert "correct_index" not in question
    assert "feedback" not in question


def test_chat_blocks_weight_loss_without_calling_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _sign_in()
    child_id = uuid4()
    monkeypatch.setattr("backend.main.get_child_record", lambda token, requested_id: _child_row(requested_id))
    monkeypatch.setattr("backend.main.list_chat_messages", lambda token, requested_id: [])
    monkeypatch.setattr(
        "backend.main.insert_chat_message",
        lambda token, requested_id, role, message: {
            "id": str(uuid4()),
            "child_id": str(requested_id),
            "role": role,
            "message": message,
            "created_at": "2026-11-07T12:00:00+00:00",
        },
    )

    def fail_if_called(*args: object, **kwargs: object) -> str:
        raise AssertionError("Groq should not be called for a weight-loss request.")

    monkeypatch.setattr("backend.chatbot.Groq", fail_if_called)
    response = client.post(
        "/chat",
        json={"child_id": str(child_id), "message": "Give me a weight loss diet."},
    )
    assert response.status_code == 200
    assert "doctor" in response.json()["response"].lower()


def test_empty_chat_message_is_rejected() -> None:
    _sign_in()
    response = client.post("/chat", json={"child_id": str(uuid4()), "message": "   "})
    assert response.status_code == 422


def test_register_requires_parent_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("Registration should stop before an account is created.")

    monkeypatch.setattr("backend.main.register_parent", fail_if_called)
    response = client.post(
        "/auth/register",
        json={"name": "Parent", "email": "parent@example.com", "password": "secret123", "consent": False},
    )
    assert response.status_code == 422


def test_empty_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    _sign_in()
    child_id = uuid4()
    monkeypatch.setattr("backend.main.get_child_record", lambda token, requested_id: _child_row(requested_id))
    monkeypatch.setattr("backend.main.list_quiz_attempts", lambda token, requested_id: [])
    monkeypatch.setattr("backend.main.list_chat_messages", lambda token, requested_id: [])
    response = client.get(f"/progress/{child_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["quizzes_completed"] == 0
    assert body["average_score_percent"] == 0
    assert body["badges"] == []
    assert body["score_trend"] == []
