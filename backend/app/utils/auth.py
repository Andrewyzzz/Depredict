"""
Authentication and authorization utilities for DePredict.
"""

import functools
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import request, jsonify, g

from ..config import Config
from ..models import Session, User


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_token(user_id: int) -> str:
    """Create a signed JWT for the given user ID."""
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    """Decorator that requires a valid Bearer token. Sets g.user."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        user = Session.get(User, payload["user_id"])
        if user is None:
            return jsonify({"error": "User not found"}), 401

        g.user = user
        return f(*args, **kwargs)
    return wrapper


def premium_required(f):
    """Decorator that requires g.user.tier == 'premium'. Use after @login_required."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not hasattr(g, "user") or g.user is None:
            return jsonify({"error": "Authentication required"}), 401
        if g.user.tier != "premium":
            return jsonify({"error": "Premium subscription required"}), 403
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Prediction limit check
# ---------------------------------------------------------------------------

def check_prediction_limit(user: User) -> bool:
    """
    Return True if the user can make a prediction.

    Premium users: always True.
    Free users: check monthly limit with lazy reset.
    """
    if user.tier == "premium":
        return True

    now = datetime.now(timezone.utc)

    # Lazy reset: if reset_at is None or in the past, reset the counter
    if user.predictions_reset_at is None or user.predictions_reset_at <= now:
        user.predictions_this_month = 0
        # Set reset to first day of next month
        if now.month == 12:
            user.predictions_reset_at = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            user.predictions_reset_at = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        Session.commit()

    return user.predictions_this_month < Config.FREE_PREDICTIONS_PER_MONTH
