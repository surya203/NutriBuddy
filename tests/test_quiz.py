"""Quiz scoring, badges, and answer hiding."""

from backend.quiz import (
    BADGE_FIRST,
    BADGE_FRUIT,
    BADGE_MASTER,
    BADGE_STAR,
    BADGE_VEGETABLE,
    check_answer,
    earned_badges,
    public_question,
    questions_for_topic,
    score_answers,
    stars_for,
)


def test_public_questions_hide_the_correct_answer() -> None:
    question = public_question(questions_for_topic("Fruits and vegetables")[0])
    assert "correct_index" not in question
    assert len(question["options"]) == 4


def test_correct_and_incorrect_answers() -> None:
    correct = check_answer("fv-1", 1)
    incorrect = check_answer("fv-1", 0)
    assert correct["correct"] is True
    assert incorrect["correct"] is False
    assert "beta-carotene" in correct["feedback"]


def test_score_and_stars() -> None:
    scored = score_answers(
        "Hydration",
        [
            {"question_id": "hy-1", "selected_index": 0},
            {"question_id": "hy-2", "selected_index": 0},
            {"question_id": "hy-3", "selected_index": 1},
        ],
    )
    assert scored["score"] == 2
    assert scored["total_questions"] == 3
    assert scored["stars"] == stars_for(2, 3) == 2


def test_empty_submission_is_rejected() -> None:
    try:
        score_answers("Hydration", [])
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Empty answers should be rejected.")


def test_badges_follow_learning_milestones() -> None:
    attempts = [
        {"topic": "Fruits and vegetables", "score": 3, "total_questions": 3},
        {"topic": "Hydration", "score": 3, "total_questions": 3},
        {"topic": "Proteins", "score": 3, "total_questions": 3},
        {"topic": "Carbohydrates", "score": 2, "total_questions": 3},
        {"topic": "Balanced meals", "score": 3, "total_questions": 3},
    ]
    badges = earned_badges(attempts)
    assert badges == [BADGE_FIRST, BADGE_FRUIT, BADGE_VEGETABLE, BADGE_STAR, BADGE_MASTER]


def test_low_scores_do_not_earn_mastery_badges() -> None:
    badges = earned_badges([{"topic": "Proteins", "score": 1, "total_questions": 3}])
    assert badges == [BADGE_FIRST]
