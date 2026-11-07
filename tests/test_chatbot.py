"""Safety checks for the nutrition chatbot."""

from backend.chatbot import build_messages, generate_reply
from backend.safety import review_child_message, review_model_reply


def test_nutrition_questions_are_allowed() -> None:
    assert review_child_message("Why should I eat vegetables?") is None
    assert review_child_message("What are proteins?") is None
    assert review_child_message("Why should I drink water?") is None


def test_medical_and_weight_loss_requests_are_blocked() -> None:
    medical = review_child_message("Can you diagnose my stomach pain?")
    weight = review_child_message("Give me a weight loss diet.")
    assert medical is not None and "doctor" in medical
    assert weight is not None and "weight" not in weight.lower() or "can't" in weight


def test_unrelated_questions_are_redirected() -> None:
    reply = review_child_message("What is the football score?")
    assert reply is not None
    assert "food" in reply


def test_empty_message_gets_a_prompt() -> None:
    reply = review_child_message("   ")
    assert reply is not None
    assert "question" in reply


def test_unsafe_model_text_is_replaced() -> None:
    reply = review_model_reply("You should lose weight and skip meals.")
    assert "lose weight" not in reply.lower()
    assert "food" in reply.lower()


def test_system_prompt_is_included() -> None:
    messages = build_messages("Ava", 8, [], "Why are fruits good for me?")
    assert messages[0]["role"] == "system"
    assert "7–9" in messages[0]["content"] or "7-9" in messages[0]["content"]
    assert messages[-1]["content"] == "Why are fruits good for me?"


def test_groq_failure_is_reported(monkeypatch) -> None:
    monkeypatch.setattr("backend.chatbot.review_child_message", lambda message: None)
    monkeypatch.setenv("GROQ_API_KEY", "")
    try:
        generate_reply("Ava", 8, [], "Why are fruits good for me?")
    except Exception as exc:
        assert type(exc).__name__ == "ChatError"
    else:
        raise AssertionError("A missing Groq key should fail clearly.")
