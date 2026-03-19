"""
API Blueprint registration.

Registers all Flask blueprints for the prediction market debater backend.
"""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all API blueprints with the Flask application."""
    from .debate import debate_bp
    from .market import market_bp
    from .report import report_bp
    from .history import history_bp

    app.register_blueprint(debate_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(history_bp)
