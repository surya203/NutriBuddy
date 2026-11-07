"""NutriBuddy FastAPI application."""

from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.auth import (
    AuthError,
    AuthenticatedParent,
    get_current_parent,
    login_parent,
    register_parent,
)
from backend.chatbot import ChatError, generate_reply
from backend.database import (
    DatabaseError,
    create_child_record,
    get_child_record,
    insert_chat_message,
    insert_quiz_attempt,
    list_chat_messages,
    list_child_records,
    list_quiz_attempts,
)
from backend.quiz import (
    QuizError,
    check_answer,
    choose_questions,
    earned_badges,
    list_topics,
    new_badges,
    percent,
    practice_note,
    public_question,
    questions_for_topic,
    score_answers,
    topics_needing_practice,
)
from backend.schemas import (
    AuthResponse,
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    ChildCreate,
    ChildRead,
    HealthResponse,
    LoginRequest,
    ProgressResponse,
    QuizAnswerRequest,
    QuizAnswerResult,
    QuizAttemptRead,
    QuizStartResponse,
    ScorePoint,
    QuizSubmitRequest,
    QuizSubmitResponse,
    RegisterRequest,
    TopicScore,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nutribuddy")

app = FastAPI(title="NutriBuddy", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DatabaseError)
def handle_database_error(request: Request, exc: DatabaseError) -> JSONResponse:
    if exc.code == "23503":
        status_code = status.HTTP_409_CONFLICT
        detail = "Register a parent account before adding a child."
    elif exc.code == "23514":
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = "That value is not valid."
    elif exc.status_code in (401, 403):
        status_code = status.HTTP_401_UNAUTHORIZED
        detail = "Invalid or expired authentication token."
    elif exc.status_code == 503:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "The database is unavailable."
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
        detail = "The database request failed."
    logger.info(
        "database_error method=%s path=%s status=%s code=%s",
        request.method,
        request.url.path,
        status_code,
        exc.code,
    )
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(QuizError)
def handle_quiz_error(request: Request, exc: QuizError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="nutribuddy")


@app.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> AuthResponse:
    try:
        result = register_parent(payload.name, payload.email, payload.password)
    except AuthError as exc:
        _raise_auth(exc)
    return AuthResponse(
        access_token=result.access_token,
        parent_id=result.parent_id,
        email=result.email or payload.email,
        name=result.name,
        confirmation_required=result.confirmation_required,
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    try:
        result = login_parent(payload.email, payload.password)
    except AuthError as exc:
        _raise_auth(exc)
    return AuthResponse(
        access_token=result.access_token,
        parent_id=result.parent_id,
        email=result.email or payload.email,
        name=result.name,
        confirmation_required=False,
    )


@app.post("/children", response_model=ChildRead, status_code=status.HTTP_201_CREATED)
def create_child(
    payload: ChildCreate,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> ChildRead:
    row = create_child_record(parent.access_token, parent.id, payload.nickname, payload.age)
    child = _owned_child(parent.id, row)
    logger.info("child_created child_id=%s", child.id)
    return child


@app.get("/children", response_model=list[ChildRead])
def list_children(
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> list[ChildRead]:
    rows = list_child_records(parent.access_token)
    return [_owned_child(parent.id, row) for row in rows if _belongs_to(parent.id, row)]


@app.get("/children/{child_id}", response_model=ChildRead)
def get_child(
    child_id: UUID,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> ChildRead:
    return _require_child(parent, child_id)


@app.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> ChatResponse:
    child = _require_child(parent, payload.child_id)
    history = [
        {"role": str(row["role"]), "message": str(row["message"])}
        for row in list_chat_messages(parent.access_token, child.id)
    ]
    try:
        reply = generate_reply(child.nickname, child.age, history, payload.message)
    except ChatError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NutriBuddy is resting. Add a Groq API key or try again in a moment.",
        ) from None
    insert_chat_message(parent.access_token, child.id, "user", payload.message)
    insert_chat_message(parent.access_token, child.id, "assistant", reply)
    logger.info("chat_reply child_id=%s characters=%s", child.id, len(payload.message))
    return ChatResponse(response=reply, child_id=child.id)


@app.get("/chat/history/{child_id}", response_model=list[ChatMessageRead])
def chat_history(
    child_id: UUID,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> list[ChatMessageRead]:
    _require_child(parent, child_id)
    rows = list_chat_messages(parent.access_token, child_id)
    return [ChatMessageRead.model_validate(row) for row in rows]


@app.get("/quiz/topics", response_model=list[str])
def quiz_topics(parent: AuthenticatedParent = Depends(get_current_parent)) -> list[str]:
    return list_topics()


@app.get("/quiz", response_model=QuizStartResponse)
def start_quiz(
    child_id: UUID = Query(),
    topic: str = Query(min_length=1),
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> QuizStartResponse:
    _require_child(parent, child_id)
    past = _topic_percents(list_quiz_attempts(parent.access_token, child_id), topic)
    questions = choose_questions(topic, past)
    return QuizStartResponse(
        topic=topic,
        questions=[public_question(question) for question in questions],
        practice_note=practice_note(past),
    )


@app.post("/quiz/answer", response_model=QuizAnswerResult)
def answer_quiz(
    payload: QuizAnswerRequest,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> QuizAnswerResult:
    _require_child(parent, payload.child_id)
    return QuizAnswerResult.model_validate(check_answer(payload.question_id, payload.selected_index))


@app.post("/quiz/submit", response_model=QuizSubmitResponse)
def submit_quiz(
    payload: QuizSubmitRequest,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> QuizSubmitResponse:
    _require_child(parent, payload.child_id)
    questions_for_topic(payload.topic)
    before = list_quiz_attempts(parent.access_token, payload.child_id)
    scored = score_answers(payload.topic, [answer.model_dump() for answer in payload.answers])
    insert_quiz_attempt(
        parent.access_token,
        payload.child_id,
        scored["topic"],
        scored["score"],
        scored["total_questions"],
    )
    after = list_quiz_attempts(parent.access_token, payload.child_id)
    scored["badges_earned"] = new_badges(before, after)
    logger.info("quiz_submitted child_id=%s score=%s", payload.child_id, scored["score"])
    return QuizSubmitResponse.model_validate(scored)


@app.get("/progress/{child_id}", response_model=ProgressResponse)
def progress(
    child_id: UUID,
    parent: AuthenticatedParent = Depends(get_current_parent),
) -> ProgressResponse:
    _require_child(parent, child_id)
    attempts = list_quiz_attempts(parent.access_token, child_id)
    messages = list_chat_messages(parent.access_token, child_id)
    user_messages = [row for row in messages if row.get("role") == "user"]
    scores = [percent(int(row["score"]), int(row["total_questions"])) for row in attempts]
    average = round(sum(scores) / len(scores), 1) if scores else 0
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in attempts:
        grouped[str(row["topic"])].append(percent(int(row["score"]), int(row["total_questions"])))
    topic_performance = [
        TopicScore(topic=topic, attempts=len(values), average_percent=round(sum(values) / len(values), 1))
        for topic, values in grouped.items()
    ]
    completed = [item.topic for item in topic_performance if item.average_percent >= 60]
    recent = list(reversed(attempts[-5:]))
    trend = [
        ScorePoint(
            topic=str(row["topic"]),
            score_percent=round(percent(int(row["score"]), int(row["total_questions"])), 1),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )
        for row in attempts
    ]
    return ProgressResponse(
        child_id=child_id,
        quizzes_completed=len(attempts),
        average_score_percent=average,
        total_learning_activities=len(attempts) + len(user_messages),
        topics_completed=completed,
        recent_attempts=[QuizAttemptRead.model_validate(row) for row in recent],
        score_trend=trend,
        topic_performance=topic_performance,
        badges=earned_badges(attempts),
        practice_topics=topics_needing_practice(attempts),
    )


def _raise_auth(exc: AuthError) -> None:
    status_code = exc.status_code if exc.status_code in (400, 401, 403, 409, 422) else status.HTTP_503_SERVICE_UNAVAILABLE
    if exc.status_code >= 500:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    raise HTTPException(status_code=status_code, detail=exc.detail)


def _require_child(parent: AuthenticatedParent, child_id: UUID) -> ChildRead:
    row = get_child_record(parent.access_token, child_id)
    if row is None or not _belongs_to(parent.id, row):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found.")
    return _owned_child(parent.id, row)


def _topic_percents(attempts: list[dict[str, object]], topic: str) -> list[float]:
    return [
        percent(int(row["score"]), int(row["total_questions"]))
        for row in attempts
        if row.get("topic") == topic
    ]


def _belongs_to(parent_id: UUID, row: dict[str, object]) -> bool:
    return str(row.get("parent_id")) == str(parent_id)


def _owned_child(parent_id: UUID, row: dict[str, object]) -> ChildRead:
    if not _belongs_to(parent_id, row):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found.")
    return ChildRead.model_validate(row)
