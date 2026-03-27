"""
Flask Blueprint for debate endpoints.

Provides endpoints to start debates, check status, retrieve results,
and stream progress via Server-Sent Events (SSE).
"""

import json
import logging
import queue
import threading
import traceback
from flask import Blueprint, request, jsonify, Response, g

logger = logging.getLogger(__name__)

from ..services.task_manager import TaskManager, DebateStatus
from ..services.prospective_tracker import ProspectiveTracker
from ..utils.auth import login_required, check_prediction_limit
from ..models import Session

debate_bp = Blueprint("debate", __name__, url_prefix="/api/debate")

# Global task manager instance (shared across requests)
task_manager = TaskManager()

# Prospective prediction tracker
_prospective_tracker = ProspectiveTracker()

# SSE subscriber management: task_id -> list[queue.Queue]
_sse_subscribers: dict[str, list[queue.Queue]] = {}
_sse_lock = threading.Lock()


def _subscribe(task_id: str) -> queue.Queue:
    """Register an SSE subscriber queue for a task."""
    q: queue.Queue = queue.Queue(maxsize=100)
    with _sse_lock:
        _sse_subscribers.setdefault(task_id, []).append(q)
    return q


def _unsubscribe(task_id: str, q: queue.Queue):
    """Remove an SSE subscriber queue."""
    with _sse_lock:
        subs = _sse_subscribers.get(task_id, [])
        if q in subs:
            subs.remove(q)


def _emit_event(task_id: str, event: dict):
    """Broadcast an SSE event to all subscribers of a task."""
    with _sse_lock:
        subs = _sse_subscribers.get(task_id, [])
        dead = []
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            subs.remove(q)


def _sse_format(data: dict) -> str:
    """Format a dict as an SSE event string."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@debate_bp.route("/start", methods=["POST"])
@login_required
def start_debate():
    """
    Start a new debate pipeline in the background.

    Body: { "question": str, "market_price": float|null }
    Returns: { "task_id": str, "status": "created" }
    """
    # Check prediction limit
    if not check_prediction_limit(g.user):
        return jsonify({
            "error": "Monthly prediction limit reached. Upgrade to premium for unlimited predictions.",
            "predictions_this_month": g.user.predictions_this_month,
            "limit": 3,
        }), 403

    data = request.get_json(force=True)
    question = data.get("question")
    if not question:
        return jsonify({"error": "question is required"}), 400

    market_price = data.get("market_price")
    slug = data.get("slug")

    # Increment prediction count
    g.user.predictions_this_month += 1
    Session.commit()

    # Create task via TaskManager
    task_state = task_manager.create_task(question, market_price=market_price)
    task_id = task_state.task_id

    # Start debate in background thread
    thread = threading.Thread(
        target=_run_debate_pipeline,
        args=(task_id, question, market_price, slug),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id, "status": "created"}), 201


@debate_bp.route("/<task_id>/status", methods=["GET"])
def get_status(task_id: str):
    """
    Get current task status.

    Returns: task state as simple dict (to_simple_dict()).
    """
    task = task_manager.get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task.to_simple_dict())


@debate_bp.route("/<task_id>/result", methods=["GET"])
def get_result(task_id: str):
    """
    Get full debate result (only if completed).

    Returns: full result dict.
    """
    task = task_manager.get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.status != DebateStatus.COMPLETED:
        return jsonify({
            "error": "result not available",
            "status": task.status.value,
        }), 400

    return jsonify(task.result)


@debate_bp.route("/<task_id>/stream", methods=["GET"])
def stream_progress(task_id: str):
    """
    SSE endpoint that streams progress events.

    Each event: { "stage": str, "percent": int, "message": str, "data": any }
    """
    task = task_manager.get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    def generate():
        """Generator that yields SSE events from the subscriber queue."""
        event_queue = _subscribe(task_id)

        # Send current state as first event
        yield _sse_format({
            "stage": task.current_stage,
            "percent": task.progress_percent,
            "message": task.progress_message,
            "data": None,
        })

        try:
            while True:
                try:
                    event = event_queue.get(timeout=30)
                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    continue

                yield _sse_format(event)

                # Stop streaming if debate is done or errored
                if event.get("stage") in ("completed", "error", "failed"):
                    break
        finally:
            _unsubscribe(task_id, event_queue)

    return Response(generate(), mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    })


def _run_debate_pipeline(task_id: str, question: str, market_price: float | None, slug: str | None = None):
    """
    Run the debate pipeline in a background thread.

    Uses the refactored DebatePipeline with progress_callback for real-time
    SSE updates and TaskManager state synchronization.
    """
    from ..core.debate_pipeline import DebatePipeline

    def progress_callback(stage: str, percent: int, message: str, **kwargs):
        """Bridge between pipeline callbacks and SSE + TaskManager."""
        data = kwargs.get("data")
        event = {
            "stage": stage,
            "percent": percent,
            "message": message,
            "agent_name": kwargs.get("agent_name"),
            "current": kwargs.get("current"),
            "total": kwargs.get("total"),
            "data": _safe_serialize(data),
        }
        _emit_event(task_id, event)
        task_manager.update_progress(
            task_id, stage, percent, message,
            agents_completed=kwargs.get("current"),
        )

    try:
        task_manager.update_progress(task_id, "retrieving", 0, "Initializing pipeline...")

        pipeline = DebatePipeline()
        result = pipeline.run(
            question,
            market_price=market_price,
            progress_callback=progress_callback,
        )

        # Save prospective prediction if we have a market price and slug
        if market_price is not None and slug:
            try:
                _prospective_tracker.save_prediction(
                    question=question,
                    slug=slug,
                    market_price=market_price,
                    debate_result=result,
                    task_id=task_id,
                )
            except Exception:
                logger.exception("Failed to save prospective prediction for slug=%s", slug)

        # Store full result
        task_manager.update_progress(
            task_id, "completed", 100, "Debate completed.",
            status=DebateStatus.COMPLETED,
            data={"result": result},
        )
        _emit_event(task_id, {
            "stage": "completed",
            "percent": 100,
            "message": "Debate completed.",
            "data": {
                "aggregated_probability": result.get("aggregated_probability"),
                "aggregation_mechanisms": {
                    k: v.get("probability")
                    for k, v in result.get("aggregation_mechanisms", {}).items()
                },
            },
        })

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        tb = traceback.format_exc()
        task_manager.update_progress(
            task_id, "failed", 0, error_msg,
            status=DebateStatus.FAILED,
            error=error_msg,
        )
        _emit_event(task_id, {
            "stage": "failed",
            "percent": 0,
            "message": error_msg,
            "data": {"traceback": tb},
        })


def _safe_serialize(obj):
    """Make data JSON-safe (strip raw_response to save bandwidth)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "raw_response":
                continue  # skip verbose LLM output in SSE
            out[k] = _safe_serialize(v)
        return out
    if isinstance(obj, list):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, set):
        return list(obj)
    return obj
