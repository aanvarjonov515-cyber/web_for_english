from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# COMMON TYPES
# =========================================================

LearningMode = Literal[
    "reading",
    "pronunciation",
    "writing",
    "listening",
]


# =========================================================
# IMPORT
# =========================================================

class ImportRequest(BaseModel):
    """
    Data received when the user imports raw vocabulary text.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    text: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description=(
            "Raw English vocabulary text pasted by the user."
        ),
        examples=[
            (
                "coffee n /'kofi/\n"
                "Daddy n /'dædi/\n"
                "day n /dei/"
            )
        ],
    )


# =========================================================
# WORD
# =========================================================

class WordResponse(BaseModel):
    """
    Standard vocabulary object returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
    )

    id: int = Field(
        ...,
        ge=1,
        description="Unique database ID.",
    )

    english: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="English word or phrase.",
    )

    pronunciation: str = Field(
        default="",
        max_length=500,
        description="Pronunciation/IPA information.",
    )

    part_of_speech: str = Field(
        default="phrase",
        max_length=50,
        description="Part of speech.",
    )

    translation: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Uzbek translation.",
    )


# =========================================================
# IMPORT RESPONSE
# =========================================================

class ImportResponse(BaseModel):
    """
    Response returned after vocabulary import.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    imported: list[WordResponse] = Field(
        default_factory=list,
        description="Successfully imported vocabulary.",
    )

    count: int = Field(
        ...,
        ge=0,
        description="Number of imported vocabulary items.",
    )


# =========================================================
# ATTEMPT REQUEST
# =========================================================

class AttemptRequest(BaseModel):
    """
    Data sent when the student submits an answer.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    word_id: int = Field(
        ...,
        ge=1,
        description="ID of the vocabulary word.",
    )

    mode: LearningMode = Field(
        ...,
        description="Learning mode used for this attempt.",
    )

    user_answer: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Answer typed by the student.",
    )


# =========================================================
# ATTEMPT RESPONSE
# =========================================================

class AttemptResponse(BaseModel):
    """
    Result returned after checking an answer.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    correct: bool = Field(
        ...,
        description="Whether the submitted answer is correct.",
    )

    correct_answer: str = Field(
        ...,
        min_length=1,
        description="Correct English answer.",
    )

    message: str = Field(
        ...,
        min_length=1,
        description="Human-readable feedback message.",
    )


# =========================================================
# STATISTICS
# =========================================================

class StatisticsResponse(BaseModel):
    """
    Global learning statistics.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    total_words: int = Field(
        default=0,
        ge=0,
    )

    total_attempts: int = Field(
        default=0,
        ge=0,
    )

    correct_attempts: int = Field(
        default=0,
        ge=0,
    )

    incorrect_attempts: int = Field(
        default=0,
        ge=0,
    )

    accuracy: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    reading_attempts: int = Field(
        default=0,
        ge=0,
    )

    pronunciation_attempts: int = Field(
        default=0,
        ge=0,
    )

    writing_attempts: int = Field(
        default=0,
        ge=0,
    )

    listening_attempts: int = Field(
        default=0,
        ge=0,
    )

    strong_words: int = Field(
        default=0,
        ge=0,
    )

    weak_words: int = Field(
        default=0,
        ge=0,
    )

    due_words: int = Field(
        default=0,
        ge=0,
    )


# =========================================================
# REVIEW STATE
# =========================================================

class ReviewStateResponse(BaseModel):
    """
    Learning state of one vocabulary word.

    This will be used by the smart review system.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    word_id: int = Field(
        ...,
        ge=1,
    )

    total_attempts: int = Field(
        default=0,
        ge=0,
    )

    correct_attempts: int = Field(
        default=0,
        ge=0,
    )

    incorrect_attempts: int = Field(
        default=0,
        ge=0,
    )

    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    difficulty: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    current_streak: int = Field(
        default=0,
        ge=0,
    )

    best_streak: int = Field(
        default=0,
        ge=0,
    )

    last_attempt_at: str | None = None

    next_review_at: str | None = None


# =========================================================
# REVIEW QUEUE ITEM
# =========================================================

class ReviewWordResponse(WordResponse):
    """
    Vocabulary item enriched with review information.
    """

    total_attempts: int = Field(
        default=0,
        ge=0,
    )

    correct_attempts: int = Field(
        default=0,
        ge=0,
    )

    incorrect_attempts: int = Field(
        default=0,
        ge=0,
    )

    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    difficulty: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    current_streak: int = Field(
        default=0,
        ge=0,
    )

    best_streak: int = Field(
        default=0,
        ge=0,
    )

    last_attempt_at: str | None = None

    next_review_at: str | None = None


# =========================================================
# SETTINGS
# =========================================================

class SettingResponse(BaseModel):
    """
    One application setting.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    value: str = Field(
        default="",
        max_length=5000,
    )


class SettingsResponse(BaseModel):
    """
    All application settings.
    """

    settings: dict[str, str] = Field(
        default_factory=dict,
    )


# =========================================================
# HEALTH
# =========================================================

class HealthResponse(BaseModel):
    """
    API health response.
    """

    status: Literal[
        "ok",
        "error",
    ]

    app: str

    version: str


# =========================================================
# DELETE RESPONSE
# =========================================================

class DeleteResponse(BaseModel):
    """
    Standard delete response.
    """

    success: bool

    message: str

    word_id: int = Field(
        ...,
        ge=1,
    )


# =========================================================
# GENERIC MESSAGE
# =========================================================

class MessageResponse(BaseModel):
    """
    Generic API message.
    """

    success: bool = True

    message: str = Field(
        ...,
        min_length=1,
    )