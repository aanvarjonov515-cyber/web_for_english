from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


# ============================================================
# GEMINI SDK
# ============================================================

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# ============================================================
# ENVIRONMENT
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

ENV_FILE = os.path.join(
    BASE_DIR,
    ".env"
)

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True
)


GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
).strip()


GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.7-flash"
).strip() or "gemini-3.7-flash"


SOURCE_LANGUAGE = os.getenv(
    "SOURCE_LANGUAGE",
    "en"
).strip().lower() or "en"


TARGET_LANGUAGE = os.getenv(
    "TARGET_LANGUAGE",
    "uz"
).strip().lower() or "uz"


# ============================================================
# EXCEPTIONS
# ============================================================

class TranslationError(Exception):
    """Base translation exception."""


class TranslationConfigurationError(TranslationError):
    """Gemini configuration is missing."""


class TranslationAuthenticationError(TranslationError):
    """Gemini authentication failed."""


class TranslationRequestError(TranslationError):
    """Gemini request failed."""


class TranslationResponseError(TranslationError):
    """Gemini returned an invalid response."""


# ============================================================
# DATA MODELS
# ============================================================

class SingleTranslationResponse(BaseModel):
    translation: str = Field(
        description="Natural Uzbek translation."
    )


class BatchTranslationResponse(BaseModel):
    translations: list[str] = Field(
        description=(
            "Uzbek translations in exactly the same order "
            "as the input English vocabulary items."
        )
    )


@dataclass(frozen=True)
class TranslationResult:
    source: str
    translation: str


# ============================================================
# CLIENT
# ============================================================

_client: Any | None = None


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> Any:
    global _client

    if _client is not None:
        return _client

    if genai is None:
        raise TranslationConfigurationError(
            "google-genai is not installed."
        )

    if not GEMINI_API_KEY:
        raise TranslationConfigurationError(
            "GEMINI_API_KEY is missing in .env."
        )

    try:
        _client = genai.Client(
            api_key=GEMINI_API_KEY
        )
    except Exception as exc:
        raise TranslationAuthenticationError(
            f"Gemini client initialization failed: {exc}"
        ) from exc

    return _client


# ============================================================
# TEXT HELPERS
# ============================================================

def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    return text.strip()


def _clean_translation(value: Any) -> str:
    text = _clean_text(value)

    # Remove accidental surrounding quotes.
    if len(text) >= 2:
        if (
            (text.startswith('"') and text.endswith('"'))
            or
            (text.startswith("'") and text.endswith("'"))
        ):
            text = text[1:-1].strip()

    # Remove accidental markdown fences.
    text = re.sub(
        r"^```(?:text)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ============================================================
# PROMPTS
# ============================================================

SINGLE_SYSTEM_INSTRUCTION = """
You are a professional English-to-Uzbek vocabulary translator.

Translate the supplied English vocabulary item into natural Uzbek.

Requirements:
- Return only the requested structured response.
- Do not explain anything.
- Do not add examples.
- Do not transliterate the English word.
- Use natural Uzbek suitable for an English learner.
- Preserve the meaning of phrases and expressions.
- For an interjection or exclamation, translate its natural meaning.
- For common words with several meanings, provide the most useful
  general Uzbek meaning.
""".strip()


BATCH_SYSTEM_INSTRUCTION = """
You are a professional English-to-Uzbek vocabulary translator.

Translate every English vocabulary item into natural Uzbek.

Requirements:
- Preserve the exact input order.
- Translate every item.
- Never omit an item.
- Never merge two items.
- Never add an item.
- Duplicate English items must remain duplicate positions.
- Return exactly one translation string for every input item.
- Do not explain anything.
- Do not add examples.
- Do not transliterate the English words.
- Use natural Uzbek suitable for an English learner.
- Translate phrases naturally.
""".strip()


# ============================================================
# GEMINI ERROR HANDLING
# ============================================================

def _raise_gemini_error(exc: Exception) -> None:
    message = str(exc)

    lowered = message.lower()

    if (
        "401" in lowered
        or "unauthenticated" in lowered
        or "api key" in lowered
        or "authentication" in lowered
    ):
        raise TranslationAuthenticationError(
            f"Gemini authentication failed: {message}"
        ) from exc

    if (
        "403" in lowered
        or "permission" in lowered
        or "forbidden" in lowered
    ):
        raise TranslationAuthenticationError(
            f"Gemini permission error: {message}"
        ) from exc

    if (
        "429" in lowered
        or "resource exhausted" in lowered
        or "rate limit" in lowered
    ):
        raise TranslationRequestError(
            f"Gemini rate limit/quota error: {message}"
        ) from exc

    if (
        "500" in lowered
        or "502" in lowered
        or "503" in lowered
        or "504" in lowered
        or "unavailable" in lowered
    ):
        raise TranslationRequestError(
            f"Gemini service temporarily unavailable: {message}"
        ) from exc

    raise TranslationRequestError(
        f"Gemini request failed: {message}"
    ) from exc


# ============================================================
# SINGLE TRANSLATION
# ============================================================

def translate_word(word: str) -> str:
    source = _clean_text(word)

    if not source:
        raise TranslationError(
            "Cannot translate an empty vocabulary item."
        )

    client = _get_client()

    prompt = (
        "Translate this English vocabulary item into Uzbek:\n\n"
        f"{source}"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SINGLE_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=SingleTranslationResponse,
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"
                ),
                max_output_tokens=1024,
            ),
        )
    except Exception as exc:
        _raise_gemini_error(exc)

    # Preferred path: SDK parsed structured response.
    parsed = getattr(
        response,
        "parsed",
        None
    )

    if parsed is not None:

        if isinstance(
            parsed,
            SingleTranslationResponse
        ):
            translation = _clean_translation(
                parsed.translation
            )

            if translation:
                return translation

        if isinstance(parsed, dict):
            translation = _clean_translation(
                parsed.get("translation")
            )

            if translation:
                return translation

    # Fallback: parse response.text through Pydantic.
    response_text = _clean_text(
        getattr(response, "text", "")
    )

    if not response_text:
        raise TranslationResponseError(
            f"Gemini returned an empty response for '{source}'."
        )

    try:
        parsed_model = (
            SingleTranslationResponse
            .model_validate_json(
                response_text
            )
        )
    except ValidationError as exc:
        raise TranslationResponseError(
            "Gemini returned invalid structured data "
            f"for '{source}': {response_text[:500]}"
        ) from exc

    translation = _clean_translation(
        parsed_model.translation
    )

    if not translation:
        raise TranslationResponseError(
            f"Gemini returned an empty translation for '{source}'."
        )

    return translation


# ============================================================
# BATCH TRANSLATION
# ============================================================

def _translate_batch_gemini(
    words: list[str],
) -> list[str]:

    client = _get_client()

    numbered_items = "\n".join(
        f"{index + 1}. {word}"
        for index, word in enumerate(words)
    )

    prompt = (
        "Translate every English vocabulary item below "
        "into natural Uzbek.\n\n"
        f"{numbered_items}"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=BATCH_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=BatchTranslationResponse,
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"
                ),
                max_output_tokens=4096,
            ),
        )
    except Exception as exc:
        _raise_gemini_error(exc)

    # Preferred structured response.
    parsed = getattr(
        response,
        "parsed",
        None
    )

    if isinstance(
        parsed,
        BatchTranslationResponse
    ):
        translations = parsed.translations

    elif isinstance(parsed, dict):
        translations = parsed.get(
            "translations"
        )

    else:
        translations = None

    if translations is None:

        response_text = _clean_text(
            getattr(response, "text", "")
        )

        if not response_text:
            raise TranslationResponseError(
                "Gemini returned an empty batch response."
            )

        try:
            parsed_model = (
                BatchTranslationResponse
                .model_validate_json(
                    response_text
                )
            )

            translations = parsed_model.translations

        except ValidationError as exc:
            raise TranslationResponseError(
                "Gemini returned invalid structured batch data: "
                f"{response_text[:1000]}"
            ) from exc

    if not isinstance(
        translations,
        list
    ):
        raise TranslationResponseError(
            "Gemini translations field is not a list."
        )

    if len(translations) != len(words):
        raise TranslationResponseError(
            "Gemini returned the wrong number of translations. "
            f"Expected {len(words)}, got {len(translations)}."
        )

    cleaned: list[str] = []

    for index, value in enumerate(translations):

        translation = _clean_translation(
            value
        )

        if not translation:
            raise TranslationResponseError(
                "Gemini returned an empty translation at "
                f"position {index + 1}."
            )

        cleaned.append(
            translation
        )

    return cleaned


# ============================================================
# BATCH PUBLIC API
# ============================================================

def translate_words(
    words: list[str],
) -> list[str]:

    if not isinstance(
        words,
        list
    ):
        raise TranslationError(
            "translate_words() expects list[str]."
        )

    cleaned_words = [
        _clean_text(word)
        for word in words
    ]

    if not cleaned_words:
        return []

    if any(
        not word
        for word in cleaned_words
    ):
        raise TranslationError(
            "Vocabulary list contains an empty item."
        )

    # --------------------------------------------------------
    # First attempt: one structured Gemini batch request.
    # --------------------------------------------------------

    try:
        return _translate_batch_gemini(
            cleaned_words
        )

    except TranslationResponseError:
        # JSON/schema problem.
        # Fall back to one-by-one translation.
        pass

    except TranslationRequestError as exc:
        # For temporary server problems, try one-by-one.
        # This avoids losing the whole import because of one
        # oversized batch response.
        temporary_message = str(exc).lower()

        if not any(
            token in temporary_message
            for token in (
                "503",
                "unavailable",
                "500",
                "502",
                "504",
                "rate limit",
                "429",
            )
        ):
            raise

    # --------------------------------------------------------
    # Reliable fallback: translate each vocabulary item
    # separately.
    # --------------------------------------------------------

    results: list[str] = []

    for word in cleaned_words:
        results.append(
            translate_word(word)
        )

    return results


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

def translate_text(
    text: str,
) -> str:
    return translate_word(
        text
    )


def translate_batch(
    words: list[str],
) -> list[str]:
    return translate_words(
        words
    )


# ============================================================
# METADATA
# ============================================================

def get_translation_metadata() -> dict[str, Any]:

    return {
        "provider": "gemini",
        "model": GEMINI_MODEL,
        "source_language": SOURCE_LANGUAGE,
        "target_language": TARGET_LANGUAGE,
        "configured": is_configured(),
        "sdk_installed": genai is not None,
        "structured_output": True,
        "thinking_level": "low",
    }


def get_translation_info() -> dict[str, Any]:
    return get_translation_metadata()


def get_configuration() -> dict[str, Any]:

    return {
        "provider": "gemini",
        "configured": is_configured(),
        "model": GEMINI_MODEL,
        "source_language": SOURCE_LANGUAGE,
        "target_language": TARGET_LANGUAGE,
    }


# ============================================================
# HEALTH
# ============================================================

def check_translation_health() -> dict[str, Any]:

    sdk_installed = genai is not None
    key_configured = bool(
        GEMINI_API_KEY
    )

    return {
        "healthy": (
            sdk_installed
            and key_configured
        ),
        "provider": "gemini",
        "model": GEMINI_MODEL,
        "configured": key_configured,
        "sdk_installed": sdk_installed,
        "structured_output": True,
        "thinking_level": "low",
        "error": (
            None
            if sdk_installed and key_configured
            else (
                "google-genai is not installed."
                if not sdk_installed
                else
                "GEMINI_API_KEY is missing."
            )
        ),
    }


# ============================================================
# DIAGNOSTIC TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("Gemini Translator Diagnostic")
    print("=" * 60)

    print(
        f"Provider: gemini"
    )

    print(
        f"Model: {GEMINI_MODEL}"
    )

    print(
        f"Configured: {is_configured()}"
    )

    print(
        f"SDK installed: {genai is not None}"
    )

    print(
        "Structured output: True"
    )

    print(
        "Thinking level: low"
    )

    print("-" * 60)

    if not is_configured():
        print(
            "Gemini translation test: FAILED"
        )

        print(
            "Error: GEMINI_API_KEY is missing in .env"
        )

        raise SystemExit(1)

    if genai is None:
        print(
            "Gemini translation test: FAILED"
        )

        print(
            "Error: google-genai is not installed."
        )

        raise SystemExit(1)

    test_words = [
        "coffee",
        "Daddy",
        "day",
        "fine",
        "Good afternoon!",
    ]

    print(
        f"Testing {len(test_words)} vocabulary items..."
    )

    try:

        translations = translate_words(
            test_words
        )

        print()
        print(
            "Translations:"
        )

        for english, uzbek in zip(
            test_words,
            translations,
        ):
            print(
                f"  {english} -> {uzbek}"
            )

        print()
        print(
            "Gemini translation test: SUCCESS"
        )

    except TranslationError as exc:

        print()
        print(
            "Gemini translation test: FAILED"
        )

        print(
            f"Error: {exc}"
        )

        raise SystemExit(1)

    print("=" * 60)