"""
Flask Blueprint for authentication endpoints.
"""

import re
import stripe
from flask import Blueprint, request, jsonify, g

from ..config import Config
from ..models import Session, User
from ..utils.auth import (
    hash_password, check_password, create_token, login_required,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_dict(user: User) -> dict:
    """Serialize a User to a safe dict for API responses."""
    return {
        "id": user.id,
        "email": user.email,
        "tier": user.tier,
        "predictions_this_month": user.predictions_this_month,
        "predictions_limit": Config.FREE_PREDICTIONS_PER_MONTH if user.tier == "free" else None,
    }


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user. Body: { email, password }"""
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not _EMAIL_RE.match(email):
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    existing = Session.query(User).filter_by(email=email).first()
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    user = User(email=email, password_hash=hash_password(password))
    Session.add(user)
    Session.commit()

    token = create_token(user.id)
    return jsonify({"token": token, "user": _user_dict(user)}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Log in. Body: { email, password }"""
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = Session.query(User).filter_by(email=email).first()
    if user is None or not check_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_token(user.id)
    return jsonify({"token": token, "user": _user_dict(user)})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Get current user info."""
    return jsonify({"user": _user_dict(g.user)})


@auth_bp.route("/create-checkout", methods=["POST"])
@login_required
def create_checkout():
    """Create a Stripe Checkout session for premium subscription."""
    stripe.api_key = Config.STRIPE_SECRET_KEY
    if not stripe.api_key:
        return jsonify({"error": "Stripe not configured"}), 503

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": Config.STRIPE_PRICE_ID, "quantity": 1}],
            customer_email=g.user.email,
            metadata={"user_id": str(g.user.id)},
            success_url=request.json.get("success_url", "http://localhost:5173/settings?session_id={CHECKOUT_SESSION_ID}"),
            cancel_url=request.json.get("cancel_url", "http://localhost:5173/settings"),
        )
        return jsonify({"checkout_url": session.url})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/create-portal", methods=["POST"])
@login_required
def create_portal():
    """Create a Stripe billing portal session."""
    stripe.api_key = Config.STRIPE_SECRET_KEY
    if not stripe.api_key:
        return jsonify({"error": "Stripe not configured"}), 503

    if not g.user.stripe_customer_id:
        return jsonify({"error": "No billing account found"}), 400

    try:
        session = stripe.billing_portal.Session.create(
            customer=g.user.stripe_customer_id,
            return_url=request.json.get("return_url", "http://localhost:5173/settings"),
        )
        return jsonify({"portal_url": session.url})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 500
