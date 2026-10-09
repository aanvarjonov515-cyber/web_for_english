from __future__ import annotations

import sys

import uvicorn

from backend.config import (
    APP_NAME,
    DEBUG,
    HOST,
    PORT,
)


def main() -> None:
    """
    Starts the English Vocabulary Trainer server.
    """

    print("=" * 60)
    print(APP_NAME)
    print("=" * 60)

    print(
        f"Server: http://{HOST}:{PORT}"
    )

    print(
        f"API docs: http://{HOST}:{PORT}/docs"
    )

    print(
        f"Health: http://{HOST}:{PORT}/api/health"
    )

    print("=" * 60)

    try:
        uvicorn.run(
            "backend.main:app",
            host=HOST,
            port=PORT,
            reload=DEBUG,
            log_level="info",
        )

    except KeyboardInterrupt:
        print(
            "\nServer stopped by user."
        )

    except Exception as exc:
        print(
            "\nServer failed to start."
        )

        print(
            f"Error: {exc}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()