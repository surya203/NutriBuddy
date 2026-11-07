"""Request and response models for the NutriBuddy API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    service: str = "nutribuddy"


class ChildCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=40)
    age: int = Field(ge=7, le=9)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nickname is required.")
        return cleaned


class ChildRead(BaseModel):
    id: UUID
    parent_id: UUID
    nickname: str
    age: int
    created_at: datetime


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=72)
    consent: bool

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name is required.")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        domain = cleaned.split("@")[-1] if "@" in cleaned else ""
        if "@" not in cleaned or "." not in domain:
            raise ValueError("Enter a valid email address.")
        return cleaned

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("A parent or guardian must agree before an account is created.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthResponse(BaseModel):
    access_token: str | None = None
    parent_id: UUID | None = None
    email: str
    name: str = ""
    confirmation_required: bool = False


class ChatRequest(BaseModel):
    child_id: UUID
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Type a question first.")
        return cleaned


class ChatResponse(BaseModel):
    response: str
    child_id: UUID


class ChatMessageRead(BaseModel):
    id: UUID
    child_id: UUID
    role: str
    message: str
    created_at: datetime


class QuizQuestionRead(BaseModel):
    id: str
    topic: str
    question: str
    options: list[str]


class QuizStartResponse(BaseModel):
    topic: str
    questions: list[QuizQuestionRead]
    practice_note: str | None = None


class QuizAnswerRequest(BaseModel):
    child_id: UUID
    question_id: str = Field(min_length=1, max_length=40)
    selected_index: int = Field(ge=0, le=3)


class QuizAnswerResult(BaseModel):
    question_id: str
    correct: bool
    correct_index: int
    feedback: str


class SubmittedAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=40)
    selected_index: int = Field(ge=0, le=3)


class QuizSubmitRequest(BaseModel):
    child_id: UUID
    topic: str = Field(min_length=1, max_length=80)
    answers: list[SubmittedAnswer]


class QuizResultItem(BaseModel):
    question_id: str
    selected_index: int
    correct_index: int
    correct: bool
    feedback: str


class QuizSubmitResponse(BaseModel):
    topic: str
    score: int
    total_questions: int
    stars: int
    results: list[QuizResultItem]
    suggestion: str
    badges_earned: list[str]


class TopicScore(BaseModel):
    topic: str
    attempts: int
    average_percent: float


class QuizAttemptRead(BaseModel):
    id: UUID
    topic: str
    score: int
    total_questions: int
    created_at: datetime


class ScorePoint(BaseModel):
    topic: str
    score_percent: float
    created_at: datetime


class ProgressResponse(BaseModel):
    child_id: UUID
    quizzes_completed: int
    average_score_percent: float
    total_learning_activities: int
    topics_completed: list[str]
    recent_attempts: list[QuizAttemptRead]
    score_trend: list[ScorePoint]
    topic_performance: list[TopicScore]
    badges: list[str]
    practice_topics: list[str]
