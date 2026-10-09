from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# PROJECT PATH
# =========================================================

BASE_DIR = Path(
    __file__
).resolve().parent.parent

ENV_FILE = BASE_DIR / ".env"


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv(ENV_FILE)


# =========================================================
# INTERNAL HELPERS
# =========================================================

def _read_int_env(
    name: str,
    default: int,
) -> int:
    """
    Safely reads an integer from environment variables.
    """

    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _read_bool_env(
    name: str,
    default: bool = False,
) -> bool:
    """
    Safely reads a boolean from environment variables.
    """

    value = os.getenv(name)

    if value is None:
        return default

    return (
        value.strip().lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


# =========================================================
# APPLICATION
# =========================================================

APP_NAME = (
    os.getenv(
        "APP_NAME",
        "English Vocabulary Trainer",
    ).strip()
    or "English Vocabulary Trainer"
)

APP_ENV = (
    os.getenv(
        "APP_ENV",
        "development",
    ).strip().lower()
    or "development"
)


# =========================================================
# SERVER
# =========================================================

HOST = (
    os.getenv(
        "HOST",
        "127.0.0.1",
    ).strip()
    or "127.0.0.1"
)

PORT = _read_int_env(
    "PORT",
    8000,
)

if not 1 <= PORT <= 65535:
    PORT = 8000


# =========================================================
# FRONTEND ORIGIN
# =========================================================

APP_ORIGIN = (
    os.getenv(
        "APP_ORIGIN",
        f"http://{HOST}:{PORT}",
    ).strip()
    or f"http://{HOST}:{PORT}"
)


# =========================================================
# DATABASE
# =========================================================

DATABASE_PATH_VALUE = (
    os.getenv(
        "DATABASE_PATH",
        "data/vocabulary.db",
    ).strip()
    or "data/vocabulary.db"
)

DATABASE_PATH = (
    BASE_DIR / DATABASE_PATH_VALUE
).resolve()


# =========================================================
# GOOGLE CLOUD TRANSLATION
# =========================================================

GOOGLE_TRANSLATE_API_KEY = (
    os.getenv(
        "GOOGLE_TRANSLATE_API_KEY",
        "",
    ).strip()
)

SOURCE_LANGUAGE = (
    os.getenv(
        "SOURCE_LANGUAGE",
        "en",
    ).strip().lower()
    or "en"
)

TARGET_LANGUAGE = (
    os.getenv(
        "TARGET_LANGUAGE",
        "uz",
    ).strip().lower()
    or "uz"
)


# =========================================================
# AUDIO
# =========================================================

AUDIO_VOICE = (
    os.getenv(
        "AUDIO_VOICE",
        "en-US-AriaNeural",
    ).strip()
    or "en-US-AriaNeural"
)

AUDIO_RATE = (
    os.getenv(
        "AUDIO_RATE",
        "+0%",
    ).strip()
    or "+0%"
)

AUDIO_PITCH = (
    os.getenv(
        "AUDIO_PITCH",
        "+0Hz",
    ).strip()
    or "+0Hz"
)


# =========================================================
# LEARNING
# =========================================================

DAILY_GOAL = max(
    1,
    _read_int_env(
        "DAILY_GOAL",
        20,
    ),
)

MAX_VOCABULARY_IMPORT = max(
    1,
    _read_int_env(
        "MAX_VOCABULARY_IMPORT",
        1000,
    ),
)

MAX_ANSWER_LENGTH = max(
    1,
    _read_int_env(
        "MAX_ANSWER_LENGTH",
        500,
    ),
)


# =========================================================
# DEVELOPMENT
# =========================================================

DEBUG = _read_bool_env(
    "DEBUG",
    False,
)


# =========================================================
# DIRECTORY INITIALIZATION
# =========================================================

def initialize_directories() -> None:
    """
    Ensures the main project directories exist.
    """

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        BASE_DIR / "audio"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        BASE_DIR / "audio" / "generated"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        BASE_DIR / "data"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )


# =========================================================
# CONFIGURATION VALIDATION
# =========================================================

def validate_config() -> None:
    """
    Validates the core application configuration.

    The Google API key is intentionally not required here.
    This allows the UI and local database to start even when
    translation has not yet been configured.
    """

    if not APP_NAME:
        raise ValueError(
            "APP_NAME cannot be empty."
        )

    if not HOST:
        raise ValueError(
            "HOST cannot be empty."
        )

    if not 1 <= PORT <= 65535:
        raise ValueError(
            "PORT must be between 1 and 65535."
        )

    if not SOURCE_LANGUAGE:
        raise ValueError(
            "SOURCE_LANGUAGE cannot be empty."
        )

    if not TARGET_LANGUAGE:
        raise ValueError(
            "TARGET_LANGUAGE cannot be empty."
        )

    if not AUDIO_VOICE:
        raise ValueError(
            "AUDIO_VOICE cannot be empty."
        )

    if not AUDIO_RATE:
        raise ValueError(
            "AUDIO_RATE cannot be empty."
        )

    if not AUDIO_PITCH:
        raise ValueError(
            "AUDIO_PITCH cannot be empty."
        )

    initialize_directories()


# =========================================================
# SAFE CONFIGURATION INFO
# =========================================================

def get_config_info() -> dict[str, str | int | bool]:
    """
    Returns safe configuration details.

    Secrets such as GOOGLE_TRANSLATE_API_KEY are never
    returned.
    """

    return {
        "app_name": APP_NAME,
        "app_env": APP_ENV,
        "host": HOST,
        "port": PORT,
        "app_origin": APP_ORIGIN,
        "database_path": str(
            DATABASE_PATH
        ),
        "source_language":
            SOURCE_LANGUAGE,
        "target_language":
            TARGET_LANGUAGE,
        "translation_configured":
            bool(
                GOOGLE_TRANSLATE_API_KEY
            ),
        "audio_voice":
            AUDIO_VOICE,
        "audio_rate":
            AUDIO_RATE,
        "audio_pitch":
            AUDIO_PITCH,
        "daily_goal":
            DAILY_GOAL,
        "max_vocabulary_import":
            MAX_VOCABULARY_IMPORT,
        "max_answer_length":
            MAX_ANSWER_LENGTH,
        "debug":
            DEBUG,
    }


# =========================================================
# STARTUP VALIDATION
# =========================================================

validate_config()