from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Any

from backend.config import DATABASE_PATH


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

def get_database_path() -> Path:
    """
    Returns the absolute database path.

    DATABASE_PATH is configured in backend/config.py.
    """
    return Path(DATABASE_PATH)


# =========================================================
# CONNECTION
# =========================================================

@contextmanager
def get_connection():
    """
    Creates a SQLite connection and automatically:

    - enables foreign keys
    - uses Row objects
    - commits on success
    - rolls back on error
    - closes the connection
    """

    db_path = get_database_path()

    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        db_path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    # Important for foreign-key relations.
    connection.execute(
        "PRAGMA foreign_keys = ON;"
    )

    # Wait for a locked database for a short time.
    connection.execute(
        "PRAGMA busy_timeout = 5000;"
    )

    try:
        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database() -> None:
    """
    Creates all required tables and indexes.

    Safe to run every time the application starts.
    """

    with get_connection() as connection:

        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            -------------------------------------------------
            -- WORDS
            -------------------------------------------------

            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                english TEXT NOT NULL,

                pronunciation TEXT
                    NOT NULL DEFAULT '',

                part_of_speech TEXT
                    NOT NULL DEFAULT 'phrase',

                translation TEXT NOT NULL,

                created_at TEXT
                    NOT NULL DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    NOT NULL DEFAULT CURRENT_TIMESTAMP
            );


            -------------------------------------------------
            -- UNIQUE ENGLISH WORD
            -------------------------------------------------

            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_words_english_unique
            ON words (
                english COLLATE NOCASE
            );


            -------------------------------------------------
            -- ATTEMPTS
            -------------------------------------------------

            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                word_id INTEGER NOT NULL,

                mode TEXT NOT NULL,

                user_answer TEXT
                    NOT NULL DEFAULT '',

                correct_answer TEXT
                    NOT NULL DEFAULT '',

                is_correct INTEGER
                    NOT NULL DEFAULT 0,

                created_at TEXT
                    NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (word_id)
                    REFERENCES words(id)
                    ON DELETE CASCADE
            );


            -------------------------------------------------
            -- ATTEMPT INDEXES
            -------------------------------------------------

            CREATE INDEX IF NOT EXISTS
            idx_attempts_word_id
            ON attempts(word_id);

            CREATE INDEX IF NOT EXISTS
            idx_attempts_mode
            ON attempts(mode);

            CREATE INDEX IF NOT EXISTS
            idx_attempts_created_at
            ON attempts(created_at);


            -------------------------------------------------
            -- REVIEW STATE
            --
            -- This table stores the learning state of each
            -- word and will later be used by the smart
            -- review / spaced repetition system.
            -------------------------------------------------

            CREATE TABLE IF NOT EXISTS review_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                word_id INTEGER NOT NULL UNIQUE,

                total_attempts INTEGER
                    NOT NULL DEFAULT 0,

                correct_attempts INTEGER
                    NOT NULL DEFAULT 0,

                incorrect_attempts INTEGER
                    NOT NULL DEFAULT 0,

                success_rate REAL
                    NOT NULL DEFAULT 0,

                difficulty REAL
                    NOT NULL DEFAULT 0.5,

                current_streak INTEGER
                    NOT NULL DEFAULT 0,

                best_streak INTEGER
                    NOT NULL DEFAULT 0,

                last_attempt_at TEXT,

                next_review_at TEXT,

                created_at TEXT
                    NOT NULL DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (word_id)
                    REFERENCES words(id)
                    ON DELETE CASCADE
            );


            -------------------------------------------------
            -- REVIEW INDEXES
            -------------------------------------------------

            CREATE INDEX IF NOT EXISTS
            idx_review_next_review
            ON review_states(next_review_at);

            CREATE INDEX IF NOT EXISTS
            idx_review_difficulty
            ON review_states(difficulty);


            -------------------------------------------------
            -- SETTINGS
            -------------------------------------------------

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,

                value TEXT
                    NOT NULL DEFAULT '',

                updated_at TEXT
                    NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


# =========================================================
# INTERNAL HELPERS
# =========================================================

def row_to_dict(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    """
    Safely converts a SQLite Row into a dictionary.
    """

    if row is None:
        return None

    return dict(row)


def get_current_utc_iso() -> str:
    """
    Returns the current UTC timestamp in ISO format.

    SQLite's CURRENT_TIMESTAMP is also UTC, but this helper
    is useful when application logic needs an explicit
    timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


# =========================================================
# WORD OPERATIONS
# =========================================================

def create_word(
    english: str,
    pronunciation: str,
    part_of_speech: str,
    translation: str,
) -> dict:
    """
    Creates a new word.

    If the English word already exists, its information is
    updated instead of creating a duplicate.

    Existing learning history is preserved.
    """

    english = english.strip()
    pronunciation = (
        pronunciation.strip()
        if pronunciation
        else ""
    )
    part_of_speech = (
        part_of_speech.strip()
        if part_of_speech
        else "phrase"
    )
    translation = translation.strip()

    if not english:
        raise ValueError(
            "English word cannot be empty."
        )

    if not translation:
        raise ValueError(
            "Translation cannot be empty."
        )

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO words (
                english,
                pronunciation,
                part_of_speech,
                translation
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(english)
            DO UPDATE SET
                pronunciation = excluded.pronunciation,
                part_of_speech = excluded.part_of_speech,
                translation = excluded.translation,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (
                english,
                pronunciation,
                part_of_speech,
                translation,
            ),
        )

        row = connection.execute(
            """
            SELECT
                id,
                english,
                pronunciation,
                part_of_speech,
                translation,
                created_at,
                updated_at
            FROM words
            WHERE lower(english) = lower(?)
            LIMIT 1;
            """,
            (english,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "Word was saved but could not be retrieved."
            )

        word_id = int(row["id"])

        # Create a review state automatically
        # for every new vocabulary item.
        connection.execute(
            """
            INSERT INTO review_states (
                word_id
            )
            VALUES (?)

            ON CONFLICT(word_id)
            DO NOTHING;
            """,
            (word_id,),
        )

    return dict(row)


def get_words() -> list[dict]:
    """
    Returns all vocabulary in insertion order.
    """

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                id,
                english,
                pronunciation,
                part_of_speech,
                translation,
                created_at,
                updated_at
            FROM words
            ORDER BY id ASC;
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_recent_words(
    limit: int = 5,
) -> list[dict]:
    """
    Returns recently added or updated words.
    """

    limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                id,
                english,
                pronunciation,
                part_of_speech,
                translation,
                created_at,
                updated_at
            FROM words
            ORDER BY id DESC
            LIMIT ?;
            """,
            (limit,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_word(
    word_id: int,
) -> dict | None:
    """
    Returns one word by ID.
    """

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                id,
                english,
                pronunciation,
                part_of_speech,
                translation,
                created_at,
                updated_at
            FROM words
            WHERE id = ?
            LIMIT 1;
            """,
            (word_id,),
        ).fetchone()

    return row_to_dict(row)


def get_word_by_english(
    english: str,
) -> dict | None:
    """
    Finds a word case-insensitively.
    """

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                id,
                english,
                pronunciation,
                part_of_speech,
                translation,
                created_at,
                updated_at
            FROM words
            WHERE lower(english) = lower(?)
            LIMIT 1;
            """,
            (english.strip(),),
        ).fetchone()

    return row_to_dict(row)


def delete_word(
    word_id: int,
) -> bool:
    """
    Deletes a word.

    Related attempts and review state are automatically
    deleted because of ON DELETE CASCADE.
    """

    with get_connection() as connection:

        cursor = connection.execute(
            """
            DELETE FROM words
            WHERE id = ?;
            """,
            (word_id,),
        )

    return cursor.rowcount > 0


def count_words() -> int:
    """
    Returns the number of vocabulary items.
    """

    with get_connection() as connection:

        result = connection.execute(
            """
            SELECT COUNT(*)
            FROM words;
            """
        ).fetchone()

    return int(result[0])


# =========================================================
# ATTEMPT OPERATIONS
# =========================================================

def create_attempt(
    word_id: int,
    mode: str,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
) -> int:
    """
    Stores a learning attempt and updates the word's review
    state.
    """

    mode = mode.strip().lower()

    allowed_modes = {
        "reading",
        "pronunciation",
        "writing",
        "listening",
    }

    if mode not in allowed_modes:
        raise ValueError(
            "Invalid learning mode."
        )

    is_correct_value = (
        1 if is_correct else 0
    )

    now = get_current_utc_iso()

    with get_connection() as connection:

        # -------------------------------------------------
        # Verify word exists
        # -------------------------------------------------

        word = connection.execute(
            """
            SELECT id
            FROM words
            WHERE id = ?
            LIMIT 1;
            """,
            (word_id,),
        ).fetchone()

        if word is None:
            raise ValueError(
                f"Word with id {word_id} does not exist."
            )

        # -------------------------------------------------
        # Save attempt
        # -------------------------------------------------

        cursor = connection.execute(
            """
            INSERT INTO attempts (
                word_id,
                mode,
                user_answer,
                correct_answer,
                is_correct,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                word_id,
                mode,
                user_answer.strip(),
                correct_answer.strip(),
                is_correct_value,
                now,
            ),
        )

        attempt_id = int(
            cursor.lastrowid
        )

        # -------------------------------------------------
        # Make sure review state exists
        # -------------------------------------------------

        connection.execute(
            """
            INSERT INTO review_states (
                word_id
            )
            VALUES (?)

            ON CONFLICT(word_id)
            DO NOTHING;
            """,
            (word_id,),
        )

        # -------------------------------------------------
        # Read old review state
        # -------------------------------------------------

        review = connection.execute(
            """
            SELECT
                total_attempts,
                correct_attempts,
                incorrect_attempts,
                current_streak,
                best_streak
            FROM review_states
            WHERE word_id = ?
            LIMIT 1;
            """,
            (word_id,),
        ).fetchone()

        if review is None:
            raise RuntimeError(
                "Review state could not be created."
            )

        total_attempts = (
            int(review["total_attempts"])
            + 1
        )

        correct_attempts = (
            int(review["correct_attempts"])
            + is_correct_value
        )

        incorrect_attempts = (
            int(review["incorrect_attempts"])
            + (
                0
                if is_correct_value
                else 1
            )
        )

        if is_correct_value:
            current_streak = (
                int(review["current_streak"])
                + 1
            )
        else:
            current_streak = 0

        best_streak = max(
            int(review["best_streak"]),
            current_streak,
        )

        success_rate = round(
            (
                correct_attempts
                / total_attempts
            ) * 100,
            2,
        )

        # -------------------------------------------------
        # Difficulty
        #
        # 0.0 = very easy
        # 1.0 = very difficult
        # -------------------------------------------------

        incorrect_rate = (
            1
            - (
                correct_attempts
                / total_attempts
            )
        )

        difficulty = round(
            max(
                0.0,
                min(
                    1.0,
                    incorrect_rate,
                ),
            ),
            4,
        )

        # -------------------------------------------------
        # Next review scheduling
        #
        # Initial version:
        #
        # Correct:
        #     +1 day
        #
        # Incorrect:
        #     same/next short review cycle
        #
        # Later this can be upgraded to a full
        # spaced repetition algorithm.
        # -------------------------------------------------

        if is_correct_value:
            review_days = min(
                7,
                max(
                    1,
                    current_streak,
                ),
            )
        else:
            review_days = 0

        if review_days > 0:
            next_review_at = (
                datetime.now(
                    timezone.utc
                )
                + __import__(
                    "datetime"
                ).timedelta(
                    days=review_days
                )
            ).isoformat()
        else:
            next_review_at = now

        # -------------------------------------------------
        # Update review state
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE review_states
            SET
                total_attempts = ?,
                correct_attempts = ?,
                incorrect_attempts = ?,
                success_rate = ?,
                difficulty = ?,
                current_streak = ?,
                best_streak = ?,
                last_attempt_at = ?,
                next_review_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE word_id = ?;
            """,
            (
                total_attempts,
                correct_attempts,
                incorrect_attempts,
                success_rate,
                difficulty,
                current_streak,
                best_streak,
                now,
                next_review_at,
                word_id,
            ),
        )

    return attempt_id


def get_attempts_for_word(
    word_id: int,
    limit: int = 50,
) -> list[dict]:
    """
    Returns the latest attempts for one word.
    """

    limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                id,
                word_id,
                mode,
                user_answer,
                correct_answer,
                is_correct,
                created_at
            FROM attempts
            WHERE word_id = ?
            ORDER BY id DESC
            LIMIT ?;
            """,
            (
                word_id,
                limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# REVIEW STATE
# =========================================================

def get_review_state(
    word_id: int,
) -> dict | None:
    """
    Returns learning/review state for a word.
    """

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                id,
                word_id,
                total_attempts,
                correct_attempts,
                incorrect_attempts,
                success_rate,
                difficulty,
                current_streak,
                best_streak,
                last_attempt_at,
                next_review_at,
                created_at,
                updated_at
            FROM review_states
            WHERE word_id = ?
            LIMIT 1;
            """,
            (word_id,),
        ).fetchone()

    return row_to_dict(row)


def get_review_queue(
    limit: int = 20,
) -> list[dict]:
    """
    Returns words that are due for review.

    Difficult words are prioritized.
    """

    limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    now = get_current_utc_iso()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                w.id,
                w.english,
                w.pronunciation,
                w.part_of_speech,
                w.translation,

                r.total_attempts,
                r.correct_attempts,
                r.incorrect_attempts,
                r.success_rate,
                r.difficulty,
                r.current_streak,
                r.best_streak,
                r.last_attempt_at,
                r.next_review_at

            FROM words AS w

            LEFT JOIN review_states AS r
                ON r.word_id = w.id

            WHERE
                r.next_review_at IS NULL
                OR r.next_review_at <= ?

            ORDER BY
                COALESCE(
                    r.difficulty,
                    1.0
                ) DESC,

                COALESCE(
                    r.total_attempts,
                    0
                ) ASC,

                w.id ASC

            LIMIT ?;
            """,
            (
                now,
                limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# STATISTICS
# =========================================================

def get_statistics() -> dict:
    """
    Returns global learning statistics.

    Compatible with the current frontend.
    """

    with get_connection() as connection:

        total_words = connection.execute(
            """
            SELECT COUNT(*)
            FROM words;
            """
        ).fetchone()[0]

        total_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts;
            """
        ).fetchone()[0]

        correct_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE is_correct = 1;
            """
        ).fetchone()[0]

        incorrect_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE is_correct = 0;
            """
        ).fetchone()[0]

        reading_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE mode = 'reading';
            """
        ).fetchone()[0]

        pronunciation_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE mode = 'pronunciation';
            """
        ).fetchone()[0]

        writing_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE mode = 'writing';
            """
        ).fetchone()[0]

        listening_attempts = connection.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE mode = 'listening';
            """
        ).fetchone()[0]

        strong_words = connection.execute(
            """
            SELECT COUNT(*)
            FROM review_states
            WHERE
                total_attempts >= 3
                AND success_rate >= 80;
            """
        ).fetchone()[0]

        weak_words = connection.execute(
            """
            SELECT COUNT(*)
            FROM review_states
            WHERE
                total_attempts > 0
                AND success_rate < 60;
            """
        ).fetchone()[0]

        due_words = connection.execute(
            """
            SELECT COUNT(*)
            FROM review_states
            WHERE
                next_review_at IS NULL
                OR next_review_at <= ?;
            """,
            (get_current_utc_iso(),),
        ).fetchone()[0]

    accuracy = (
        round(
            (
                correct_attempts
                / total_attempts
            ) * 100,
            1,
        )
        if total_attempts
        else 0.0
    )

    return {
        # Current frontend fields.
        "total_words": int(
            total_words
        ),

        "total_attempts": int(
            total_attempts
        ),

        "correct_attempts": int(
            correct_attempts
        ),

        "incorrect_attempts": int(
            incorrect_attempts
        ),

        "accuracy": accuracy,

        # Future dashboard fields.
        "reading_attempts": int(
            reading_attempts
        ),

        "pronunciation_attempts": int(
            pronunciation_attempts
        ),

        "writing_attempts": int(
            writing_attempts
        ),

        "listening_attempts": int(
            listening_attempts
        ),

        "strong_words": int(
            strong_words
        ),

        "weak_words": int(
            weak_words
        ),

        "due_words": int(
            due_words
        ),
    }


def get_mode_statistics() -> dict:
    """
    Returns performance separately for each learning mode.
    """

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                mode,

                COUNT(*) AS attempts,

                SUM(
                    CASE
                        WHEN is_correct = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS correct,

                SUM(
                    CASE
                        WHEN is_correct = 0
                        THEN 1
                        ELSE 0
                    END
                ) AS incorrect

            FROM attempts

            GROUP BY mode

            ORDER BY mode ASC;
            """
        ).fetchall()

    result: dict[str, dict] = {}

    for row in rows:

        attempts = int(
            row["attempts"] or 0
        )

        correct = int(
            row["correct"] or 0
        )

        incorrect = int(
            row["incorrect"] or 0
        )

        accuracy = (
            round(
                (
                    correct
                    / attempts
                ) * 100,
                1,
            )
            if attempts
            else 0.0
        )

        result[row["mode"]] = {
            "attempts": attempts,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy,
        }

    return result


# =========================================================
# SETTINGS
# =========================================================

def set_setting(
    key: str,
    value: str,
) -> None:
    """
    Saves an application setting.
    """

    key = key.strip()

    if not key:
        raise ValueError(
            "Setting key cannot be empty."
        )

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO settings (
                key,
                value,
                updated_at
            )
            VALUES (?, ?, CURRENT_TIMESTAMP)

            ON CONFLICT(key)
            DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (
                key,
                str(value),
            ),
        )


def get_setting(
    key: str,
    default: str | None = None,
) -> str | None:
    """
    Reads one application setting.
    """

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT value
            FROM settings
            WHERE key = ?
            LIMIT 1;
            """,
            (key,),
        ).fetchone()

    if row is None:
        return default

    return str(row["value"])


def get_all_settings() -> dict[str, str]:
    """
    Returns all application settings.
    """

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                key,
                value
            FROM settings
            ORDER BY key ASC;
            """
        ).fetchall()

    return {
        str(row["key"]): str(row["value"])
        for row in rows
    }


# =========================================================
# DATABASE MAINTENANCE
# =========================================================

def clear_all_data() -> None:
    """
    Deletes all vocabulary, attempts, reviews and settings.

    Intended for development/testing.
    """

    with get_connection() as connection:

        connection.execute(
            "DELETE FROM attempts;"
        )

        connection.execute(
            "DELETE FROM review_states;"
        )

        connection.execute(
            "DELETE FROM words;"
        )

        connection.execute(
            "DELETE FROM settings;"
        )

        # Reset AUTOINCREMENT counters.
        connection.execute(
            """
            DELETE FROM sqlite_sequence
            WHERE name IN (
                'words',
                'attempts',
                'review_states'
            );
            """
        )


def vacuum_database() -> None:
    """
    Reclaims unused SQLite database space.

    This operation is normally used during maintenance,
    not after every request.
    """

    db_path = get_database_path()

    # VACUUM cannot run inside the context manager transaction,
    # so use a dedicated connection.
    connection = sqlite3.connect(
        db_path,
        timeout=30,
    )

    try:
        connection.execute(
            "VACUUM;"
        )

        connection.commit()

    finally:
        connection.close()


# =========================================================
# OPTIONAL DEBUG INFORMATION
# =========================================================

def get_database_info() -> dict:
    """
    Returns basic database information useful for debugging.
    """

    db_path = get_database_path()

    with get_connection() as connection:

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name ASC;
            """
        ).fetchall()

    return {
        "path": str(db_path),
        "exists": db_path.exists(),
        "size_bytes": (
            db_path.stat().st_size
            if db_path.exists()
            else 0
        ),
        "tables": [
            row["name"]
            for row in tables
        ],
    }