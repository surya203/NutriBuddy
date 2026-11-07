"""Input and output checks for the child nutrition chatbot."""

from __future__ import annotations

MEDICAL_REPLY = (
    "I can't help with illnesses, medicines, or diets. "
    "Please talk with a parent or a doctor about health worries. "
    "I can still teach you about everyday foods that help you grow!"
)

OFF_TOPIC_REPLY = (
    "I'm NutriBuddy, so I love questions about food and eating. "
    "Want to ask me about fruits, water, or what protein does?"
)

KIND_REPLY = (
    "Every food can teach us something. "
    "Different foods help your body grow, play, and learn. "
    "What food would you like to learn about?"
)

_MEDICAL_TERMS = (
    "diagnos",
    "medicine",
    "medication",
    "supplement",
    "weight loss",
    "lose weight",
    "diet pill",
    "calorie deficit",
    "skip meals",
    "stop eating",
    "overweight",
    "obesity",
    "anorex",
    "purge",
)

_OFF_TOPIC_TERMS = (
    "football score",
    "video game",
    "movie star",
    "celebrity",
    "homework",
    "math problem",
    "who won",
)

_SHAME_TERMS = (
    "you are bad",
    "bad child",
    "shouldn't have eaten",
    "should not have eaten",
    "junk food is bad and you",
    "you eat too much",
    "you are fat",
    "you're fat",
    "lose weight",
    "weight-loss",
    "weight loss",
    "restrict",
    "skip breakfast",
    "stop eating",
)


def review_child_message(message: str) -> str | None:
    """Return a fixed safe reply when the message should not reach the model."""
    text = message.strip()
    if not text:
        return "Type a food question and I will help you learn."
    lowered = text.lower()
    if any(term in lowered for term in _MEDICAL_TERMS):
        return MEDICAL_REPLY
    if any(term in lowered for term in _OFF_TOPIC_TERMS):
        return OFF_TOPIC_REPLY
    return None


def review_model_reply(reply: str) -> str:
    """Replace replies that give medical advice or shame a child."""
    cleaned = " ".join(reply.split())
    if not cleaned:
        return KIND_REPLY
    lowered = cleaned.lower()
    if any(term in lowered for term in _MEDICAL_TERMS) or any(term in lowered for term in _SHAME_TERMS):
        return KIND_REPLY
    if len(cleaned) > 900:
        return cleaned[:900].rsplit(" ", 1)[0] + "..."
    return cleaned
