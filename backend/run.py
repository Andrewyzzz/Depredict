"""
Entry point for the prediction-market-debater backend server.
"""

import os
import sys

# UTF-8 encoding fix for Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# Ensure the backend directory is on sys.path so `app` is importable
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app import create_app
from app.config import Config
from app.utils.logger import get_logger

logger = get_logger("run")


def main() -> None:
    """Validate config and start the Flask-SocketIO server."""
    errors = Config.validate()
    if errors:
        logger.warning("Configuration issues detected:")
        for err in errors:
            logger.warning("  - %s", err)
    else:
        logger.info("Configuration OK")

    backends = Config.get_available_backends()
    logger.info("Available LLM backends: %s", backends if backends else "(none)")

    app = create_app()

    # Import socketio after create_app() has initialized it
    from app import socketio

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"

    logger.info("Starting server on %s:%d (debug=%s)", host, port, debug)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
