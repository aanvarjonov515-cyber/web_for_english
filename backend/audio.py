from __future__ import annotations

import asyncio
from pathlib import Path
import re
from typing import Final

try:
    import edge_tts
except ImportError:
    edge_tts = None


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent

AUDIO_DIR: Final[Path] = (
    BASE_DIR / "audio" / "generated"
)

DEFAULT_VOICE: Final[str] = (
    "en-US-AriaNeural"
)

DEFAULT_RATE: Final[str] = (
    "+0%"
)

DEFAULT_PITCH: Final[str] = (
    "+0Hz"
)


# =========================================================
# EXCEPTIONS
# =========================================================

class AudioError(Exception):
    """Base audio service error."""


class AudioDependencyError(
    AudioError
):
    """Audio dependency is unavailable."""


class AudioGenerationError(
    AudioError
):
    """Audio generation failed."""


# =========================================================
# DIRECTORY
# =========================================================

def initialize_audio_directory() -> None:
    """
    Creates the directory used for generated audio files.
    """

    AUDIO_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_audio_text(
    text: str,
) -> str:
    """
    Cleans text before sending it to the TTS engine.
    """

    if text is None:
        return ""

    value = str(text)

    value = re.sub(
        r"[\r\n\t]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# =========================================================
# SAFE FILE NAME
# =========================================================

def make_safe_filename(
    text: str,
) -> str:
    """
    Creates a safe filename from a vocabulary word.

    Example:

        Good afternoon!

    becomes:

        good_afternoon
    """

    value = normalize_audio_text(
        text
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    value = value.strip(
        "_"
    )

    if not value:
        value = "word"

    return value


def get_audio_path(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> Path:
    """
    Returns the deterministic path for a generated
    pronunciation file.
    """

    safe_text = make_safe_filename(
        text
    )

    safe_voice = make_safe_filename(
        voice
    )

    safe_rate = make_safe_filename(
        rate
    )

    safe_pitch = make_safe_filename(
        pitch
    )

    filename = (
        f"{safe_text}__"
        f"{safe_voice}__"
        f"{safe_rate}__"
        f"{safe_pitch}.mp3"
    )

    return AUDIO_DIR / filename


# =========================================================
# DEPENDENCY CHECK
# =========================================================

def check_audio_dependency() -> None:
    """
    Makes sure the TTS package is installed.
    """

    if edge_tts is None:
        raise AudioDependencyError(
            "edge-tts is not installed. "
            "Run: pip install edge-tts"
        )


# =========================================================
# AUDIO GENERATION
# =========================================================

async def generate_audio(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    overwrite: bool = False,
) -> Path:
    """
    Generates an MP3 pronunciation file.

    Existing cached audio is reused unless overwrite=True.
    """

    check_audio_dependency()

    clean_text = normalize_audio_text(
        text
    )

    if not clean_text:
        raise AudioGenerationError(
            "Cannot generate audio for empty text."
        )

    initialize_audio_directory()

    output_path = get_audio_path(
        text=clean_text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )

    if (
        output_path.exists()
        and output_path.stat().st_size > 0
        and not overwrite
    ):
        return output_path

    try:
        communicator = edge_tts.Communicate(
            clean_text,
            voice,
            rate=rate,
            pitch=pitch,
        )

        await communicator.save(
            str(output_path)
        )

    except Exception as exc:
        raise AudioGenerationError(
            f"Failed to generate audio: {exc}"
        ) from exc

    if (
        not output_path.exists()
        or output_path.stat().st_size == 0
    ):
        raise AudioGenerationError(
            "Audio generation completed but "
            "the output file is empty."
        )

    return output_path


# =========================================================
# SYNCHRONOUS WRAPPER
# =========================================================

def generate_audio_sync(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    overwrite: bool = False,
) -> Path:
    """
    Synchronous wrapper for scripts and utility calls.
    """

    return asyncio.run(
        generate_audio(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            overwrite=overwrite,
        )
    )


# =========================================================
# BATCH AUDIO GENERATION
# =========================================================

async def generate_audio_batch(
    words: list[str],
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    overwrite: bool = False,
) -> list[Path]:
    """
    Generates pronunciation audio for multiple words.

    Existing cached files are reused.
    Original word order is preserved.
    """

    if not words:
        return []

    unique_words: list[str] = []
    seen: set[str] = set()

    for word in words:
        clean_word = normalize_audio_text(
            word
        )

        if not clean_word:
            continue

        key = clean_word.lower()

        if key in seen:
            continue

        seen.add(key)

        unique_words.append(
            clean_word
        )

    results: list[Path] = []

    for word in unique_words:
        path = await generate_audio(
            text=word,
            voice=voice,
            rate=rate,
            pitch=pitch,
            overwrite=overwrite,
        )

        results.append(
            path
        )

    return results


# =========================================================
# CHECK CACHE
# =========================================================

def audio_exists(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> bool:
    """
    Returns True if cached audio already exists.
    """

    path = get_audio_path(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )

    return (
        path.exists()
        and path.stat().st_size > 0
    )


# =========================================================
# DELETE ONE AUDIO FILE
# =========================================================

def delete_audio(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> bool:
    """
    Deletes cached audio for one word.
    """

    path = get_audio_path(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )

    if not path.exists():
        return False

    path.unlink()

    return True


# =========================================================
# CLEAR AUDIO CACHE
# =========================================================

def clear_audio_cache() -> int:
    """
    Deletes all generated MP3 files.

    Returns number of deleted files.
    """

    initialize_audio_directory()

    deleted = 0

    for path in AUDIO_DIR.glob(
        "*.mp3"
    ):
        try:
            path.unlink()
            deleted += 1
        except OSError:
            continue

    return deleted


# =========================================================
# AUDIO FILE URL
# =========================================================

def audio_filename(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> str:
    """
    Returns only the generated filename.

    Useful when exposing the file through FastAPI.
    """

    return get_audio_path(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    ).name


# =========================================================
# DIAGNOSTICS
# =========================================================

def get_audio_service_info() -> dict:
    """
    Returns safe information about the audio service.
    """

    initialize_audio_directory()

    generated_files = list(
        AUDIO_DIR.glob(
            "*.mp3"
        )
    )

    return {
        "provider": "edge-tts",
        "available": edge_tts is not None,
        "default_voice": DEFAULT_VOICE,
        "default_rate": DEFAULT_RATE,
        "default_pitch": DEFAULT_PITCH,
        "audio_directory": str(
            AUDIO_DIR
        ),
        "cached_files": len(
            generated_files
        ),
    }

# =========================================================
# AUDIO HEALTH CHECK
# =========================================================

def check_audio_health() -> dict:
    """
    Checks whether the audio service can be loaded.
    """

    info = get_audio_service_info()
    available = bool(info["available"])

    return {
        "healthy": available,
        "configured": available,
        "available": available,
        "provider": info["provider"],
        "voice": info["default_voice"],
        "rate": info["default_rate"],
        "pitch": info["default_pitch"],
        "cached_files": info["cached_files"],
        "error": (
            None
            if available
            else "edge-tts is not installed."
        ),
    }
