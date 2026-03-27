"""
Flask Blueprint for Stripe webhook handling.
"""

import logging

import stripe
from flask import Blueprint, request, jsonify

from ..config import Config
from ..models import Session, User

logger = logging.getLogger(__name__)

stripe_bp = Blueprint("stripe", __name__, url_prefix="/api/stripe")


@stripe_bp.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Stripe webhook events."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    stripe.api_key = Config.STRIPE_SECRET_KEY

    if not Config.STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "Webhook secret not configured"}), 503

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, Config.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data_object)
    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        _handle_subscription_change(data_object)

    return jsonify({"status": "ok"}), 200


def _handle_checkout_completed(session_obj: dict):
    """Upgrade user to premium after successful checkout."""
    user_id = session_obj.get("metadata", {}).get("user_id")
    if not user_id:
        logger.warning("checkout.session.completed without user_id in metadata")
        return

    user = Session.get(User, int(user_id))
    if user is None:
        logger.warning("checkout.session.completed for unknown user_id=%s", user_id)
        return

    user.tier = "premium"
    user.stripe_customer_id = session_obj.get("customer")
    user.stripe_subscription_id = session_obj.get("subscription")
    Session.commit()
    logger.info("User %s upgraded to premium", user_id)


def _handle_subscription_change(subscription_obj: dict):
    """Update user tier based on subscription status."""
    customer_id = subscription_obj.get("customer")
    if not customer_id:
        return

    user = Session.query(User).filter_by(stripe_customer_id=customer_id).first()
    if user is None:
        logger.warning("Subscription event for unknown customer_id=%s", customer_id)
        return

    status = subscription_obj.get("status", "")
    if status in ("active", "trialing"):
        user.tier = "premium"
    else:
        user.tier = "free"

    user.stripe_subscription_id = subscription_obj.get("id")
    Session.commit()
    logger.info("User %s subscription status=%s, tier=%s", user.id, status, user.tier)
