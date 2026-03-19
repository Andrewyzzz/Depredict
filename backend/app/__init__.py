"""
Flask application factory for prediction-market-debater.

NOTE: Flask imports are deferred to create_app() so that submodules
(config, services, core) can be imported without Flask installed.
"""

socketio = None


def create_app():
    """Create and configure the Flask application."""
    import os
    import sys

    from flask import Flask
    from flask_cors import CORS
    from flask_socketio import SocketIO

    from .config import Config

    global socketio
    socketio = SocketIO()

    # Validate config on startup
    errors = Config.validate()
    if errors:
        print("Configuration warnings:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    app = Flask(__name__)

    # Apply config to Flask
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["JSON_AS_ASCII"] = Config.JSON_AS_ASCII

    # Ensure upload / results directories exist
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.RESULTS_DIR, exist_ok=True)

    # CORS - allow all origins in development
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # SocketIO for real-time progress updates
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    # Register blueprints
    _register_blueprints(app)

    return app


def _register_blueprints(app):
    """Import and register API blueprints."""
    try:
        from .api.debate import debate_bp
        app.register_blueprint(debate_bp)
    except Exception as e:
        print(f"  Skipping debate_bp: {e}")

    try:
        from .api.market import market_bp
        app.register_blueprint(market_bp)
    except Exception as e:
        print(f"  Skipping market_bp: {e}")

    try:
        from .api.report import report_bp
        app.register_blueprint(report_bp)
    except Exception as e:
        print(f"  Skipping report_bp: {e}")

    try:
        from .api.history import history_bp
        app.register_blueprint(history_bp)
    except Exception as e:
        print(f"  Skipping history_bp: {e}")
