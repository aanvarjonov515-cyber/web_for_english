from __future__ import annotations

import asyncio
import inspect
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


# ============================================================================
# PROJECT IMPORTS
# ============================================================================

# Normal package import
try:
    from . import database
    from .config import (
        APP_NAME,
        APP_ORIGIN,
        DEBUG,
        HOST,
        PORT,
        initialize_directories,
    )
    from .models import (
        AttemptRequest,
        ImportRequest,
        ImportResponse,
        WordResponse,
    )
    from .translator import (
        TranslationError,
        check_translation_health,
        get_translation_metadata,
        translate_words,
    )
except ImportError:
    # Allows the file to be inspected/run directly from some IDE setups.
    from backend import database
    from backend.config import (
        APP_NAME,
        APP_ORIGIN,
        DEBUG,
        HOST,
        PORT,
        initialize_directories,
    )
    from backend.models import (
        AttemptRequest,
        ImportRequest,
        ImportResponse,
        WordResponse,
    )
    from backend.translator import (
        TranslationError,
        check_translation_health,
        get_translation_metadata,
        translate_words,
    )


# ============================================================================
# AUDIO IMPORT
# ============================================================================

try:
    try:
        from .audio import (
            AUDIO_DIR,
            AudioError,
            check_audio_health,
            generate_audio,
        )
    except ImportError:
        from backend.audio import (
            AUDIO_DIR,
            AudioError,
            check_audio_health,
            generate_audio,
        )
except Exception:

    AUDIO_DIR = (
        Path(__file__).resolve().parent.parent
        / "audio"
        / "generated"
    )

    AUDIO_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    class AudioError(Exception):
        """Fallback audio error."""

    def check_audio_health() -> dict[str, Any]:
        return {
            "healthy": False,
            "configured": False,
            "error": "Audio module is unavailable.",
        }

    def generate_audio(
        text: str,
        *args: Any,
        **kwargs: Any,
    ) -> Path:
        raise AudioError(
            "Audio module is unavailable."
        )


# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"

AUDIO_DIR = Path(AUDIO_DIR)

FRONTEND_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def _find_database_function(
    *names: str,
):
    """
    Finds the first available callable from backend.database.
    """

    for name in names:
        function = getattr(
            database,
            name,
            None,
        )

        if callable(function):
            return function

    return None


def _call_database_function(
    names: tuple[str, ...],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Calls a database function.

    Supports small differences in function signatures so the
    API remains compatible with the existing database.py.
    """

    function = _find_database_function(
        *names
    )

    if function is None:
        raise RuntimeError(
            "Database function not found: "
            + ", ".join(names)
        )

    # First attempt:
    try:
        return function(
            *args,
            **kwargs,
        )
    except TypeError:
        pass

    # Second attempt:
    # pass only kwargs that the function actually accepts.
    try:
        signature = inspect.signature(
            function
        )
    except Exception:
        raise

    accepted_kwargs: dict[str, Any] = {}

    for parameter_name in signature.parameters:
        if parameter_name in kwargs:
            accepted_kwargs[
                parameter_name
            ] = kwargs[
                parameter_name
            ]

    return function(
        *args,
        **accepted_kwargs,
    )


def _initialize_database() -> None:
    """
    Initializes the existing database layer.
    """

    function = _find_database_function(
        "initialize_database",
        "init_database",
        "initialize_db",
        "init_db",
        "create_tables",
        "setup_database",
    )

    if function is None:
        return

    try:
        result = function()

        if inspect.isawaitable(result):
            # Database initialization should normally be synchronous.
            # The existing database.py is expected to be synchronous.
            return

    except TypeError:
        # Some possible initialize functions may require parameters.
        return


# ============================================================================
# VOCABULARY PARSER
# ============================================================================

POS_VALUES = {
    "n",
    "v",
    "adj",
    "adv",
    "prep",
    "pron",
    "det",
    "conj",
    "excl",
    "phrase",
    "phr",
    "aux",
    "modal",
    "num",
    "int",
    "art",
}


def _clean_input_line(
    line: str,
) -> str:
    """
    Cleans one vocabulary line.

    Examples:

        1. coffee n /kofi/
        25) Daddy n /dadi/
        coffee n
    """

    text = str(line)

    text = text.replace(
        "\ufeff",
        "",
    )

    text = text.replace(
        "\r",
        "",
    )

    text = text.strip()

    # Remove numbering.
    text = re.sub(
        r"^\s*\d+\s*[\.\)]\s*",
        "",
        text,
    )

    return text.strip()


def _extract_pronunciation(
    text: str,
) -> tuple[str, str]:
    """
    Extracts pronunciation between /.../.

    Example:

        coffee n /'kofi/

    becomes:

        left = coffee n
        pronunciation = /'kofi/
    """

    match = re.search(
        r"/([^/\r\n]*)/",
        text,
    )

    if match is None:
        return (
            text.strip(),
            "",
        )

    pronunciation = (
        "/"
        + match.group(1).strip()
        + "/"
    )

    left = (
        text[:match.start()]
        + text[match.end():]
    ).strip()

    return (
        left,
        pronunciation,
    )


def _extract_word_and_pos(
    left: str,
) -> tuple[str, str]:
    """
    Extracts English vocabulary and part of speech.

    Examples:

        coffee n
        Daddy n
        fine adj
        Good afternoon! excl

    If no POS is provided, "phrase" is used.
    """

    tokens = left.split()

    if not tokens:
        return (
            "",
            "phrase",
        )

    last_token = (
        tokens[-1]
        .strip()
        .lower()
    )

    if last_token in POS_VALUES:
        english = " ".join(
            tokens[:-1]
        ).strip()

        if english:
            return (
                english,
                last_token,
            )

    return (
        left.strip(),
        "phrase",
    )


def parse_vocabulary(
    text: str,
) -> list[dict[str, str]]:
    """
    Parses the vocabulary input while preserving order.
    """

    if not isinstance(
        text,
        str,
    ):
        return []

    parsed: list[
        dict[str, str]
    ] = []

    for raw_line in text.splitlines():

        line = _clean_input_line(
            raw_line
        )

        if not line:
            continue

        left, pronunciation = (
            _extract_pronunciation(
                line
            )
        )

        english, part_of_speech = (
            _extract_word_and_pos(
                left
            )
        )

        english = english.strip()

        if not english:
            continue

        parsed.append(
            {
                "english": english,
                "pronunciation": pronunciation,
                "part_of_speech": part_of_speech,
            }
        )

    return parsed


# ============================================================================
# DATABASE ROW HELPERS
# ============================================================================

def _row_to_dict(
    row: Any,
) -> dict[str, Any]:
    """
    Converts common row formats to dict.
    """

    if isinstance(
        row,
        dict,
    ):
        return row

    if hasattr(
        row,
        "_asdict",
    ):
        try:
            return dict(
                row._asdict()
            )
        except Exception:
            pass

    if hasattr(
        row,
        "__dict__",
    ):
        try:
            return dict(
                vars(row)
            )
        except Exception:
            pass

    return {
        "id": 0,
        "english": str(row),
        "pronunciation": "",
        "part_of_speech": "phrase",
        "translation": "",
    }


def _word_response(
    row: Any,
) -> WordResponse:

    data = _row_to_dict(
        row
    )

    return WordResponse(
        id=int(
            data.get(
                "id",
                0,
            )
        ),
        english=str(
            data.get(
                "english",
                "",
            )
        ),
        pronunciation=str(
            data.get(
                "pronunciation",
                "",
            )
            or ""
        ),
        part_of_speech=str(
            data.get(
                "part_of_speech",
                "",
            )
            or ""
        ),
        translation=str(
            data.get(
                "translation",
                "",
            )
            or ""
        ),
    )


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(
    application: FastAPI,
):
    """
    Application startup/shutdown.
    """

    try:
        initialize_directories()
    except Exception as exc:
        print(
            "Directory initialization warning:",
            exc,
        )

    try:
        _initialize_database()
    except Exception as exc:
        print(
            "Database initialization warning:",
            exc,
        )

    print(
        f"{APP_NAME} started."
    )

    yield

    print(
        f"{APP_NAME} stopped."
    )


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title=APP_NAME,
    description=(
        "AI-powered English Vocabulary Trainer "
        "using Gemini for English-to-Uzbek translation."
    ),
    version="1.1.0",
    debug=DEBUG,
    lifespan=lifespan,
)


# ============================================================================
# CORS
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        APP_ORIGIN,
        f"http://{HOST}:{8000}",
        f"http://127.0.0.1:{8000}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# STATIC FILES
# ============================================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(
            FRONTEND_DIR
        )
    ),
    name="static",
)

app.mount(
    "/audio",
    StaticFiles(
        directory=str(
            AUDIO_DIR
        )
    ),
    name="audio",
)


# ============================================================================
# HOME
# ============================================================================

@app.get(
    "/",
    include_in_schema=False,
)
async def home():
    index_file = (
        FRONTEND_DIR
        / "index.html"
    )

    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "frontend/index.html "
                "was not found."
            ),
        )

    return FileResponse(
        str(index_file)
    )


# ============================================================================
# HEALTH
# ============================================================================

@app.get(
    "/api/health",
)
async def health():
    try:
        translation_health = (
            check_translation_health()
        )
    except Exception as exc:
        translation_health = {
            "healthy": False,
            "provider": "gemini",
            "error": str(exc),
        }

    try:
        audio_health = (
            check_audio_health()
        )
    except Exception as exc:
        audio_health = {
            "healthy": False,
            "error": str(exc),
        }

    return {
        "status": "ok",
        "application": APP_NAME,
        "translation": translation_health,
        "audio": audio_health,
    }


# ============================================================================
# AUDIO HEALTH
# ============================================================================

@app.get(
    "/api/audio/health",
)
async def audio_health():
    try:
        return check_audio_health()
    except Exception as exc:
        return {
            "healthy": False,
            "error": str(exc),
        }


# ============================================================================
# IMPORT VOCABULARY
# ============================================================================

@app.post(
    "/api/import",
    response_model=ImportResponse,
)
async def import_words(
    payload: ImportRequest,
) -> ImportResponse:
    """
    Parses vocabulary,
    translates it with Gemini,
    then saves it into SQLite.

    IMPORTANT:
    translate_words() is synchronous,
    therefore it is executed with asyncio.to_thread().
    This fixes the old:
        await translate_words(...)
    problem.
    """

    # ------------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------------

    parsed = parse_vocabulary(
        payload.text
    )

    if not parsed:
        raise HTTPException(
            status_code=400,
            detail=(
                "No vocabulary entries were detected. "
                "Example: coffee n /kɒfi/"
            ),
        )

    english_words = [
        item["english"]
        for item in parsed
    ]

    # ------------------------------------------------------------------------
    # Gemini translation
    # ------------------------------------------------------------------------

    try:
        translations = await asyncio.to_thread(
            translate_words,
            english_words,
        )

    except TranslationError as exc:

        print(
            "GEMINI TRANSLATION ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        print(
            "UNEXPECTED TRANSLATION ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected translation error: "
                + str(exc)
            ),
        ) from exc

    # ------------------------------------------------------------------------
    # Validate translation count
    # ------------------------------------------------------------------------

    if len(translations) != len(
        parsed
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "Translation result count does not "
                "match vocabulary count."
            ),
        )

    # ------------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------------

    imported: list[
        WordResponse
    ] = []

    for item, translation in zip(
        parsed,
        translations,
    ):

        try:
            saved = _call_database_function(
                (
                    "create_word",
                    "add_word",
                    "insert_word",
                ),
                english=item[
                    "english"
                ],
                pronunciation=item.get(
                    "pronunciation",
                    "",
                ),
                part_of_speech=item.get(
                    "part_of_speech",
                    "phrase",
                ),
                translation=translation,
            )

        except Exception as exc:

            print(
                "DATABASE SAVE ERROR:",
                repr(exc),
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Vocabulary was translated, "
                    "but saving failed: "
                    + str(exc)
                ),
            ) from exc

        imported.append(
            _word_response(
                saved
            )
        )

    # ------------------------------------------------------------------------
    # Return
    # ------------------------------------------------------------------------

    return ImportResponse(
        imported=imported,
        count=len(imported),
    )


# ============================================================================
# GET ALL WORDS
# ============================================================================

@app.get(
    "/api/words",
)
async def get_all_words():
    try:

        rows = _call_database_function(
            (
                "get_all_words",
                "list_words",
                "fetch_all_words",
                "get_words",
            )
        )

        if rows is None:
            rows = []

        return [
            _word_response(row)
            for row in rows
        ]

    except Exception as exc:

        print(
            "GET WORDS ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================================
# GET SINGLE WORD
# ============================================================================

@app.get(
    "/api/words/{word_id}",
)
async def get_single_word(
    word_id: int,
):
    try:

        row = _call_database_function(
            (
                "get_word",
                "get_word_by_id",
                "fetch_word",
            ),
            word_id,
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Word not found.",
            )

        return _word_response(
            row
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "GET SINGLE WORD ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================================
# DELETE WORD
# ============================================================================

@app.delete(
    "/api/words/{word_id}",
)
async def remove_word(
    word_id: int,
):
    try:

        result = _call_database_function(
            (
                "delete_word",
                "remove_word",
            ),
            word_id,
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as exc:

        print(
            "DELETE WORD ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================================
# AUDIO
# ============================================================================

@app.get(
    "/api/audio",
)
async def get_audio(
    text: str,
):
    text = str(
        text
    ).strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text is required.",
        )

    try:

        # generate_audio() in the current audio module
        # is expected to return a Path/string.
        result = await asyncio.to_thread(
            generate_audio,
            text,
        )

        # Support both sync and async implementations.
        if inspect.isawaitable(
            result
        ):
            result = await result

        audio_path = Path(
            str(result)
        )

        if not audio_path.exists():
            raise AudioError(
                "Generated audio file was not found."
            )

        return FileResponse(
            str(audio_path),
            media_type="audio/mpeg",
            filename=audio_path.name,
        )

    except AudioError as exc:

        print(
            "AUDIO ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        print(
            "UNEXPECTED AUDIO ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================================
# AUDIO CHECK
# ============================================================================

@app.get(
    "/api/audio/check",
)
async def check_audio():
    try:
        return check_audio_health()

    except Exception as exc:
        return {
            "healthy": False,
            "error": str(exc),
        }


# ============================================================================
# ATTEMPT
# ============================================================================

@app.post(
    "/api/attempt",
)
async def submit_attempt(
    payload: AttemptRequest,
):
    """
    Saves a learning attempt.

    Compatible with the existing database layer.
    """

    data = payload.model_dump()

    word_id = data.get(
        "word_id"
    )

    mode = data.get(
        "mode",
        "",
    )

    answer = data.get(
        "answer",
        "",
    )

    correct = data.get(
        "correct"
    )

    # Try common existing database function names.
    function = _find_database_function(
        "save_attempt",
        "record_attempt",
        "create_attempt",
        "add_attempt",
    )

    if function is None:
        return {
            "success": True,
            "word_id": word_id,
            "mode": mode,
            "answer": answer,
            "correct": correct,
        }

    try:

        result = _call_database_function(
            (
                "save_attempt",
                "record_attempt",
                "create_attempt",
                "add_attempt",
            ),
            word_id=word_id,
            mode=mode,
            answer=answer,
            correct=correct,
        )

        if isinstance(
            result,
            dict,
        ):
            return result

        return {
            "success": True,
            "result": result,
            "word_id": word_id,
            "mode": mode,
            "answer": answer,
            "correct": correct,
        }

    except Exception as exc:

        print(
            "ATTEMPT ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================================
# STATISTICS
# ============================================================================

@app.get(
    "/api/statistics",
)
async def statistics():
    try:

        result = _call_database_function(
            (
                "get_statistics",
                "statistics",
                "get_stats",
            )
        )

        if isinstance(
            result,
            dict,
        ):
            return result

        return {
            "total_words": 0,
            "learned_words": 0,
            "mastered_words": 0,
            "total_attempts": 0,
            "correct_attempts": 0,
            "accuracy": 0,
        }

    except Exception as exc:

        print(
            "STATISTICS ERROR:",
            repr(exc),
        )

        return {
            "total_words": 0,
            "learned_words": 0,
            "mastered_words": 0,
            "total_attempts": 0,
            "correct_attempts": 0,
            "accuracy": 0,
            "error": str(exc),
        }


# ============================================================================
# TRANSLATION INFO
# ============================================================================

@app.get(
    "/api/translation/info",
)
async def translation_info():
    try:
        return get_translation_metadata()
    except Exception as exc:
        return {
            "provider": "gemini",
            "configured": False,
            "error": str(exc),
        }


# ============================================================================
# DIRECT START
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info",
    )