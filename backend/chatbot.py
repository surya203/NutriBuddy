"""NutriBuddy conversation generation through Groq."""

from __future__ import annotations

import logging
import os

from groq import Groq

from backend.safety import review_child_message, review_model_reply

logger = logging.getLogger("nutribuddy.chatbot")

SYSTEM_PROMPT = """You are NutriBuddy, a friendly nutrition education companion for children aged 7–9.

Your purpose is to teach children about healthy eating and nutrition.

Communication guidelines:
- Use simple English.
- Keep answers short and understandable.
- Use friendly and encouraging language.
- Use examples children understand.
- Explain unfamiliar nutrition terms.
- Encourage curiosity.
- Use occasional appropriate emojis.
- Never shame children about food choices.

Safety guidelines:
- Do not diagnose medical conditions.
- Do not prescribe medication or supplements.
- Do not recommend weight-loss diets or restrictive eating.
- Do not provide personalized medical nutrition plans.
- Do not make claims that foods cure diseases.
- Do not ask children for personal or sensitive information.
- For medical concerns, encourage the child to speak with a parent or qualified healthcare professional.
- Redirect unrelated conversations toward nutrition education.

Your goal is to make nutrition education fun, safe, and understandable.
"""


class ChatError(Exception):
    """The language model could not produce a reply."""


def build_messages(
    nickname: str,
    age: int,
    history: list[dict[str, str]],
    question: str,
) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                f"The child is {age} years old and uses the nickname {nickname}. "
                "Use the nickname only sometimes. Do not ask for any other personal information."
            ),
        },
    ]
    for item in history[-8:]:
        role = item.get("role")
        text = item.get("message", "")
        if role in ("user", "assistant") and text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": question})
    return messages


def generate_reply(
    nickname: str,
    age: int,
    history: list[dict[str, str]],
    question: str,
) -> str:
    blocked = review_child_message(question)
    if blocked is not None:
        return blocked

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
    if not api_key or api_key.startswith("your_"):
        raise ChatError("missing_key")

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=build_messages(nickname, age, history, question),
            temperature=0.4,
            max_tokens=300,
        )
        content = completion.choices[0].message.content
    except Exception:
        logger.warning("Groq request failed")
        raise ChatError("provider") from None

    reply = content if isinstance(content, str) else ""
    return review_model_reply(reply)
