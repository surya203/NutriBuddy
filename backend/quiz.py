"""Reviewed nutrition quiz questions, scoring, and badges."""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

QUIZ_PATH = Path(__file__).resolve().parents[1] / "data" / "quiz_questions.json"

BADGE_FIRST = "First Quiz Completed"
BADGE_FRUIT = "Fruit Explorer"
BADGE_VEGETABLE = "Vegetable Champion"
BADGE_STAR = "Nutrition Star"
BADGE_MASTER = "Quiz Master"
FRUIT_TOPIC = "Fruits and vegetables"


class QuizError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@lru_cache
def load_questions() -> tuple[dict[str, Any], ...]:
    payload = json.loads(QUIZ_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise QuizError(500, "The quiz bank could not be read.")
    return tuple(payload)


def list_topics() -> list[str]:
    topics: list[str] = []
    for question in load_questions():
        topic = str(question["topic"])
        if topic not in topics:
            topics.append(topic)
    return topics


def questions_for_topic(topic: str) -> list[dict[str, Any]]:
    matches = [question for question in load_questions() if question["topic"] == topic]
    if not matches:
        raise QuizError(404, "That quiz topic was not found.")
    return matches


def choose_questions(topic: str, past_percents: list[float], count: int = 3) -> list[dict[str, Any]]:
    pool = questions_for_topic(topic)
    average = sum(past_percents) / len(past_percents) if past_percents else None
    if average is not None and average < 60:
        preferred = [question for question in pool if question["difficulty"] == "easy"]
    elif average is not None and average >= 80:
        preferred = [question for question in pool if question["difficulty"] == "hard"]
    else:
        preferred = pool
    if len(preferred) < count:
        preferred = pool
    return random.sample(preferred, k=min(count, len(preferred)))


def public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question["id"],
        "topic": question["topic"],
        "question": question["question"],
        "options": question["options"],
    }


def practice_note(past_percents: list[float]) -> str | None:
    if not past_percents:
        return None
    average = sum(past_percents) / len(past_percents)
    if average < 60:
        return "Let's practice this topic with some friendly questions."
    if average >= 80:
        return "You know this topic well. Here are some trickier questions."
    return None


def check_answer(question_id: str, selected_index: int) -> dict[str, Any]:
    question = _question_by_id(question_id)
    _validate_index(question, selected_index)
    correct_index = int(question["correct_index"])
    return {
        "question_id": question_id,
        "correct": selected_index == correct_index,
        "correct_index": correct_index,
        "feedback": question["feedback"],
    }


def score_answers(topic: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    if not answers:
        raise QuizError(422, "Choose an answer for each question.")
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for answer in answers:
        question_id = str(answer["question_id"])
        if question_id in seen:
            raise QuizError(422, "Each question can be answered once.")
        seen.add(question_id)
        question = _question_by_id(question_id)
        if question["topic"] != topic:
            raise QuizError(422, "Those answers do not match this quiz topic.")
        selected_index = int(answer["selected_index"])
        _validate_index(question, selected_index)
        correct_index = int(question["correct_index"])
        results.append(
            {
                "question_id": question_id,
                "selected_index": selected_index,
                "correct_index": correct_index,
                "correct": selected_index == correct_index,
                "feedback": question["feedback"],
            }
        )
    score = sum(1 for result in results if result["correct"])
    total = len(results)
    return {
        "topic": topic,
        "score": score,
        "total_questions": total,
        "stars": stars_for(score, total),
        "results": results,
        "suggestion": suggestion_for(topic, score, total),
    }


def stars_for(score: int, total: int) -> int:
    if total <= 0:
        return 0
    percent = (score / total) * 100
    if percent >= 90:
        return 3
    if percent >= 60:
        return 2
    return 1


def suggestion_for(topic: str, score: int, total: int) -> str:
    percent = (score / total) * 100 if total else 0
    if percent < 60:
        return f"Nice try. Another {topic.lower()} activity will help these ideas stick."
    if percent >= 80:
        return "Wonderful work. You can try a new food topic next."
    return "Good learning. You can practice this topic again or try a new one."


def percent(score: int, total: int) -> float:
    if total <= 0:
        return 0
    return (score / total) * 100


def earned_badges(attempts: list[dict[str, Any]]) -> list[str]:
    badges: list[str] = []
    if not attempts:
        return badges
    badges.append(BADGE_FIRST)
    fruit_scores = [_percent_of(attempt) for attempt in attempts if attempt["topic"] == FRUIT_TOPIC]
    if any(score >= 60 for score in fruit_scores):
        badges.append(BADGE_FRUIT)
    if any(score == 100 for score in fruit_scores):
        badges.append(BADGE_VEGETABLE)
    if len(attempts) >= 3:
        average = sum(_percent_of(attempt) for attempt in attempts) / len(attempts)
        if average >= 80:
            badges.append(BADGE_STAR)
    if len(attempts) >= 5:
        badges.append(BADGE_MASTER)
    return badges


def new_badges(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[str]:
    previous = set(earned_badges(before))
    return [badge for badge in earned_badges(after) if badge not in previous]


def topics_needing_practice(attempts: list[dict[str, Any]]) -> list[str]:
    by_topic: dict[str, list[float]] = {}
    for attempt in attempts:
        by_topic.setdefault(str(attempt["topic"]), []).append(_percent_of(attempt))
    weak = [
        topic
        for topic, scores in by_topic.items()
        if sum(scores) / len(scores) < 60
    ]
    unseen = [topic for topic in list_topics() if topic not in by_topic]
    return (weak + unseen)[:3]


def _question_by_id(question_id: str) -> dict[str, Any]:
    for question in load_questions():
        if question["id"] == question_id:
            return question
    raise QuizError(404, "That quiz question was not found.")


def _validate_index(question: dict[str, Any], selected_index: int) -> None:
    options = question["options"]
    if selected_index < 0 or selected_index >= len(options):
        raise QuizError(422, "Choose one of the answer buttons.")


def _percent_of(attempt: dict[str, Any]) -> float:
    return percent(int(attempt["score"]), int(attempt["total_questions"]))
