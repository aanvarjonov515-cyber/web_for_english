from __future__ import annotations

import re
import unicodedata
from typing import Any

from backend.database import (
    create_attempt,
    get_review_state,
)


# =========================================================
# CONSTANTS
# =========================================================

SUPPORTED_MODES = {
    "reading",
    "pronunciation",
    "writing",
    "listening",
}


CORRECT_MESSAGE = {
    "reading": "Great reading!",
    "pronunciation": "Great pronunciation practice!",
    "writing": "Excellent! Correct answer.",
    "listening": "Excellent listening!",
}


INCORRECT_MESSAGE = {
    "reading": "Keep reading and try again.",
    "pronunciation": "Listen carefully and try again.",
    "writing": "Not quite. Try again.",
    "listening": "Not quite. Listen again and try again.",
}


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_unicode(text: str) -> str:
    """
    Normalizes Unicode characters.

    Example:
        curly apostrophe ’
        straight apostrophe '

    are treated consistently.
    """

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    replacements = {
        "’": "'",
        "‘": "'",
        "ʼ": "'",
        "ʹ": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    return text


def normalize_answer(
    value: str,
) -> str:
    """
    Converts a user's answer into a comparable form.

    Examples:

        " Hello "
        "hello"
        "HELLO!"
        "hello."

    all become:

        "hello"
    """

    if value is None:
        return ""

    text = normalize_unicode(
        str(value)
    )

    text = text.strip().lower()

    # Remove IPA-style slashes accidentally typed
    # by the learner.
    text = text.strip("/")

    # Replace line breaks/tabs with spaces.
    text = re.sub(
        r"[\r\n\t]+",
        " ",
        text,
    )

    # Normalize common punctuation to spaces.
    text = re.sub(
        r"[.,!?;:\"()\[\]{}<>]+",
        " ",
        text,
    )

    # Keep apostrophes inside words.
    # Example:
    # don't
    # I'm
    # you're
    text = re.sub(
        r"\s*'\s*",
        "'",
        text,
    )

    # Normalize hyphens.
    text = re.sub(
        r"\s*-\s*",
        "-",
        text,
    )

    # Collapse multiple spaces.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_expected_answer(
    value: str,
) -> str:
    """
    Normalizes the correct English answer.

    This is intentionally kept separate from
    normalize_answer() so that future versions can
    support alternative correct answers.
    """

    return normalize_answer(
        value
    )


# =========================================================
# ANSWER COMPARISON
# =========================================================

def answers_match(
    user_answer: str,
    correct_answer: str,
) -> bool:
    """
    Exact semantic-text comparison after normalization.

    We do NOT use fuzzy matching here.

    Why?

    Because in vocabulary learning:

        hello

    and

        yellow

    must not accidentally be accepted as the same word.
    """

    user_normalized = normalize_answer(
        user_answer
    )

    correct_normalized = normalize_expected_answer(
        correct_answer
    )

    if not user_normalized:
        return False

    if not correct_normalized:
        return False

    return (
        user_normalized
        == correct_normalized
    )


# =========================================================
# ALTERNATIVE ANSWERS
# =========================================================

def build_acceptable_answers(
    word: dict[str, Any],
) -> set[str]:
    """
    Returns all accepted English answers for a word.

    Currently only the original English word is accepted.

    This function exists so later we can support:
        - British / American variants
        - abbreviations
        - optional punctuation
        - teacher-approved alternatives
    """

    english = word.get(
        "english",
        "",
    )

    normalized = normalize_expected_answer(
        english
    )

    if not normalized:
        return set()

    return {
        normalized,
    }


def is_answer_correct(
    word: dict[str, Any],
    user_answer: str,
) -> bool:
    """
    Checks whether the user's answer matches any
    accepted English answer.
    """

    user_normalized = normalize_answer(
        user_answer
    )

    if not user_normalized:
        return False

    accepted_answers = (
        build_acceptable_answers(
            word
        )
    )

    return (
        user_normalized
        in accepted_answers
    )


# =========================================================
# ANSWER CHECKING
# =========================================================

def check_answer(
    word: dict[str, Any],
    user_answer: str,
) -> dict[str, Any]:
    """
    Checks an answer and returns a detailed result.

    Returned structure:

        {
            "correct": bool,
            "user_answer": "...",
            "normalized_user_answer": "...",
            "correct_answer": "...",
            "normalized_correct_answer": "...",
        }
    """

    english = str(
        word.get(
            "english",
            "",
        )
    )

    normalized_user = normalize_answer(
        user_answer
    )

    normalized_correct = (
        normalize_expected_answer(
            english
        )
    )

    correct = is_answer_correct(
        word,
        user_answer,
    )

    return {
        "correct": correct,
        "user_answer": str(
            user_answer
        ).strip(),
        "normalized_user_answer":
            normalized_user,
        "correct_answer": english,
        "normalized_correct_answer":
            normalized_correct,
    }


# =========================================================
# DIFFICULTY CALCULATION
# =========================================================

def calculate_difficulty(
    total_attempts: int,
    correct_attempts: int,
) -> float:
    """
    Calculates word difficulty.

    Range:

        0.0 = very easy
        1.0 = very difficult

    Important:
        With very little data, the system keeps the
        difficulty near the middle instead of making
        a premature decision.
    """

    total_attempts = max(
        0,
        int(total_attempts),
    )

    correct_attempts = max(
        0,
        int(correct_attempts),
    )

    if total_attempts == 0:
        return 0.5

    correct_attempts = min(
        correct_attempts,
        total_attempts,
    )

    success_rate = (
        correct_attempts
        / total_attempts
    )

    difficulty = (
        1.0
        - success_rate
    )

    return round(
        max(
            0.0,
            min(
                1.0,
                difficulty,
            ),
        ),
        4,
    )


# =========================================================
# MASTERY LEVEL
# =========================================================

def get_mastery_level(
    total_attempts: int,
    correct_attempts: int,
    current_streak: int = 0,
) -> str:
    """
    Converts learning statistics into a simple
    human-readable mastery level.

    Levels:

        new
        learning
        developing
        strong
        mastered
    """

    total_attempts = max(
        0,
        int(total_attempts),
    )

    correct_attempts = max(
        0,
        int(correct_attempts),
    )

    current_streak = max(
        0,
        int(current_streak),
    )

    if total_attempts == 0:
        return "new"

    accuracy = (
        correct_attempts
        / total_attempts
    )

    if (
        total_attempts >= 5
        and accuracy >= 0.90
        and current_streak >= 3
    ):
        return "mastered"

    if (
        total_attempts >= 3
        and accuracy >= 0.80
    ):
        return "strong"

    if (
        total_attempts >= 2
        and accuracy >= 0.60
    ):
        return "developing"

    return "learning"


# =========================================================
# REVIEW PRIORITY
# =========================================================

def calculate_review_priority(
    review_state: dict[str, Any] | None,
) -> float:
    """
    Calculates a priority score for review.

    Higher score = should be reviewed sooner.

    The score considers:

        - difficulty
        - lack of attempts
        - low success rate
        - current review status
    """

    if not review_state:
        return 1.0

    attempts = int(
        review_state.get(
            "total_attempts",
            0,
        )
        or 0
    )

    success_rate = float(
        review_state.get(
            "success_rate",
            0,
        )
        or 0
    )

    difficulty = float(
        review_state.get(
            "difficulty",
            0.5,
        )
        or 0.5
    )

    # New words have high review priority.
    new_word_bonus = (
        0.35
        if attempts == 0
        else 0.0
    )

    # Lower accuracy means higher priority.
    accuracy_component = (
        1
        - (
            success_rate
            / 100
        )
    )

    priority = (
        difficulty * 0.45
        + accuracy_component * 0.45
        + new_word_bonus
    )

    return round(
        max(
            0.0,
            min(
                1.0,
                priority,
            ),
        ),
        4,
    )


# =========================================================
# NEXT REVIEW INTERVAL
# =========================================================

def calculate_next_review_days(
    correct: bool,
    current_streak: int,
    difficulty: float,
) -> int:
    """
    Calculates a simple review interval.

    Current version:

        incorrect:
            0 days

        correct:
            1 day
            2 days
            4 days
            7 days

    Difficult words progress more slowly.

    This is deliberately simple for version 1.
    A more advanced spaced-repetition algorithm can later
    replace this function without changing the frontend API.
    """

    difficulty = max(
        0.0,
        min(
            1.0,
            float(difficulty),
        ),
    )

    current_streak = max(
        0,
        int(current_streak),
    )

    if not correct:
        return 0

    base_intervals = [
        1,
        2,
        4,
        7,
    ]

    index = min(
        current_streak,
        len(base_intervals) - 1,
    )

    days = base_intervals[index]

    if difficulty >= 0.75:
        days = min(
            days,
            2,
        )

    elif difficulty >= 0.50:
        days = min(
            days,
            4,
        )

    return max(
        1,
        days,
    )


# =========================================================
# FULL ATTEMPT EVALUATION
# =========================================================

def evaluate_attempt(
    word: dict[str, Any],
    mode: str,
    user_answer: str,
) -> dict[str, Any]:
    """
    Main learning-engine entry point.

    Process:

        1. Validate mode
        2. Check answer
        3. Save attempt
        4. Read updated review state
        5. Calculate mastery
        6. Return frontend-ready result
    """

    mode = (
        str(mode)
        .strip()
        .lower()
    )

    if mode not in SUPPORTED_MODES:
        raise ValueError(
            "Invalid learning mode. "
            f"Allowed modes: "
            f"{', '.join(sorted(SUPPORTED_MODES))}."
        )

    word_id = word.get(
        "id"
    )

    if word_id is None:
        raise ValueError(
            "Word ID is required."
        )

    result = check_answer(
        word=word,
        user_answer=user_answer,
    )

    correct = bool(
        result["correct"]
    )

    english = str(
        word.get(
            "english",
            "",
        )
    )

    # -----------------------------------------------------
    # Save attempt
    # -----------------------------------------------------

    attempt_id = create_attempt(
        word_id=int(word_id),
        mode=mode,
        user_answer=str(
            user_answer
        ).strip(),
        correct_answer=english,
        is_correct=correct,
    )

    # -----------------------------------------------------
    # Get updated review state
    # -----------------------------------------------------

    review_state = get_review_state(
        int(word_id)
    )

    if review_state:
        total_attempts = int(
            review_state.get(
                "total_attempts",
                0,
            )
            or 0
        )

        correct_attempts = int(
            review_state.get(
                "correct_attempts",
                0,
            )
            or 0
        )

        incorrect_attempts = int(
            review_state.get(
                "incorrect_attempts",
                0,
            )
            or 0
        )

        current_streak = int(
            review_state.get(
                "current_streak",
                0,
            )
            or 0
        )

        best_streak = int(
            review_state.get(
                "best_streak",
                0,
            )
            or 0
        )

        success_rate = float(
            review_state.get(
                "success_rate",
                0,
            )
            or 0
        )

        difficulty = float(
            review_state.get(
                "difficulty",
                0.5,
            )
            or 0.5
        )

        mastery = get_mastery_level(
            total_attempts=total_attempts,
            correct_attempts=correct_attempts,
            current_streak=current_streak,
        )

        review_priority = (
            calculate_review_priority(
                review_state
            )
        )

    else:
        total_attempts = 1
        correct_attempts = (
            1 if correct else 0
        )
        incorrect_attempts = (
            0 if correct else 1
        )
        current_streak = (
            1 if correct else 0
        )
        best_streak = current_streak
        success_rate = (
            100.0 if correct else 0.0
        )
        difficulty = (
            calculate_difficulty(
                total_attempts,
                correct_attempts,
            )
        )
        mastery = get_mastery_level(
            total_attempts,
            correct_attempts,
            current_streak,
        )
        review_priority = 1.0

    # -----------------------------------------------------
    # Next review estimate
    # -----------------------------------------------------

    next_review_days = (
        calculate_next_review_days(
            correct=correct,
            current_streak=current_streak,
            difficulty=difficulty,
        )
    )

    # -----------------------------------------------------
    # Frontend message
    # -----------------------------------------------------

    if correct:
        message = CORRECT_MESSAGE[
            mode
        ]
    else:
        message = INCORRECT_MESSAGE[
            mode
        ]

    return {
        "attempt_id": attempt_id,

        "correct": correct,

        "user_answer": result[
            "user_answer"
        ],

        "correct_answer": result[
            "correct_answer"
        ],

        "message": message,

        "mode": mode,

        "word_id": int(
            word_id
        ),

        # Learning statistics.
        "total_attempts":
            total_attempts,

        "correct_attempts":
            correct_attempts,

        "incorrect_attempts":
            incorrect_attempts,

        "success_rate":
            round(
                success_rate,
                2,
            ),

        "difficulty":
            round(
                difficulty,
                4,
            ),

        "current_streak":
            current_streak,

        "best_streak":
            best_streak,

        "mastery":
            mastery,

        "review_priority":
            review_priority,

        "next_review_days":
            next_review_days,

        "should_review_again":
            not correct,
    }


# =========================================================
# REVIEW DECISION
# =========================================================

def should_review_word(
    review_state: dict[str, Any] | None,
) -> bool:
    """
    Determines whether a word should be considered for
    another learning cycle.
    """

    if not review_state:
        return True

    attempts = int(
        review_state.get(
            "total_attempts",
            0,
        )
        or 0
    )

    success_rate = float(
        review_state.get(
            "success_rate",
            0,
        )
        or 0
    )

    difficulty = float(
        review_state.get(
            "difficulty",
            0.5,
        )
        or 0.5
    )

    if attempts == 0:
        return True

    if success_rate < 80:
        return True

    if difficulty >= 0.50:
        return True

    return False


# =========================================================
# LEARNING SESSION ORDER
# =========================================================

def get_learning_order(
    words: list[dict[str, Any]],
    shuffle: bool = True,
) -> list[dict[str, Any]]:
    """
    Creates the vocabulary order for a learning session.

    Version 1:

        - optionally shuffle
        - keep all submitted vocabulary
        - never duplicate items

    Later this can be replaced with a full intelligent
    review queue.
    """

    cleaned_words = [
        word
        for word in words
        if word.get("english")
    ]

    if not shuffle:
        return list(
            cleaned_words
        )

    # Import locally so this module remains lightweight.
    import random

    result = list(
        cleaned_words
    )

    random.shuffle(
        result
    )

    return result


# =========================================================
# STUDY MODE VALIDATION
# =========================================================

def validate_mode(
    mode: str,
) -> str:
    """
    Validates and returns a normalized learning mode.
    """

    normalized = (
        str(mode)
        .strip()
        .lower()
    )

    if normalized not in SUPPORTED_MODES:
        raise ValueError(
            "Invalid learning mode."
        )

    return normalized


# =========================================================
# WORD LEARNING SUMMARY
# =========================================================

def build_word_learning_summary(
    word: dict[str, Any],
) -> dict[str, Any]:
    """
    Combines word information with its current learning
    state.
    """

    word_id = word.get(
        "id"
    )

    if word_id is None:
        raise ValueError(
            "Word ID is required."
        )

    review = get_review_state(
        int(word_id)
    )

    if review is None:
        return {
            "word_id": int(
                word_id
            ),
            "english": word.get(
                "english",
                "",
            ),
            "translation": word.get(
                "translation",
                "",
            ),
            "pronunciation": word.get(
                "pronunciation",
                "",
            ),
            "mastery": "new",
            "difficulty": 0.5,
            "success_rate": 0.0,
            "total_attempts": 0,
            "correct_attempts": 0,
            "incorrect_attempts": 0,
            "current_streak": 0,
            "best_streak": 0,
            "review_priority": 1.0,
            "should_review": True,
        }

    total_attempts = int(
        review.get(
            "total_attempts",
            0,
        )
        or 0
    )

    correct_attempts = int(
        review.get(
            "correct_attempts",
            0,
        )
        or 0
    )

    current_streak = int(
        review.get(
            "current_streak",
            0,
        )
        or 0
    )

    difficulty = float(
        review.get(
            "difficulty",
            0.5,
        )
        or 0.5
    )

    success_rate = float(
        review.get(
            "success_rate",
            0,
        )
        or 0
    )

    mastery = get_mastery_level(
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        current_streak=current_streak,
    )

    priority = calculate_review_priority(
        review
    )

    return {
        "word_id": int(
            word_id
        ),
        "english": word.get(
            "english",
            "",
        ),
        "translation": word.get(
            "translation",
            "",
        ),
        "pronunciation": word.get(
            "pronunciation",
            "",
        ),
        "mastery": mastery,
        "difficulty": round(
            difficulty,
            4,
        ),
        "success_rate": round(
            success_rate,
            2,
        ),
        "total_attempts":
            total_attempts,
        "correct_attempts":
            correct_attempts,
        "incorrect_attempts": int(
            review.get(
                "incorrect_attempts",
                0,
            )
            or 0
        ),
        "current_streak":
            current_streak,
        "best_streak": int(
            review.get(
                "best_streak",
                0,
            )
            or 0
        ),
        "review_priority":
            priority,
        "should_review":
            should_review_word(
                review
            ),
    }