"""
Flask Blueprint for report generation endpoints.

Generates structured prediction reports after a debate completes.
"""

import threading
from flask import Blueprint, jsonify

from ..services.task_manager import TaskManager, DebateStatus

report_bp = Blueprint("report", __name__, url_prefix="/api/report")

# Shared task manager (same instance as debate blueprint)
# In production, use a proper DI container or app context
task_manager = TaskManager()

# In-memory report storage: task_id -> {"status": str, "markdown": str|None, "sections": list}
_reports: dict[str, dict] = {}


@report_bp.route("/<task_id>/generate", methods=["POST"])
def generate_report(task_id: str):
    """
    Start report generation for a completed debate task.

    Returns: { "status": "generating" }
    """
    task = task_manager.get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.status != DebateStatus.COMPLETED:
        return jsonify({
            "error": "debate must be completed before generating report",
            "current_status": task.status.value,
        }), 400

    # Check if report is already being generated
    if task_id in _reports and _reports[task_id]["status"] == "generating":
        return jsonify({"status": "generating", "message": "report generation already in progress"})

    # Initialize report state
    _reports[task_id] = {
        "status": "generating",
        "markdown": None,
        "sections": [],
    }

    # Start report generation in background
    thread = threading.Thread(
        target=_generate_report_background,
        args=(task_id, task),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "generating"})


@report_bp.route("/<task_id>", methods=["GET"])
def get_report(task_id: str):
    """
    Get the generated report markdown, or status if still generating.

    Returns: { "status": str, "markdown": str|null }
    """
    if task_id not in _reports:
        # Check if the task exists at all
        task = task_manager.get_task(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify({
            "status": "not_started",
            "markdown": None,
            "message": "report has not been generated yet, POST to /generate first",
        })

    report = _reports[task_id]
    return jsonify({
        "status": report["status"],
        "markdown": report["markdown"],
    })


@report_bp.route("/<task_id>/sections", methods=["GET"])
def get_report_sections(task_id: str):
    """
    Get list of individual report sections (for incremental display).

    Returns: { "status": str, "sections": list[{"title": str, "content": str}] }
    """
    if task_id not in _reports:
        task = task_manager.get_task(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify({
            "status": "not_started",
            "sections": [],
        })

    report = _reports[task_id]
    return jsonify({
        "status": report["status"],
        "sections": report["sections"],
    })


def _generate_report_background(task_id: str, task):
    """Run ReportAgent in a background thread."""
    try:
        from ..services.report_agent import ReportAgent

        agent = ReportAgent(task)
        markdown = agent.generate_report()

        # Parse sections from generated markdown
        sections = _parse_sections(markdown)

        _reports[task_id] = {
            "status": "completed",
            "markdown": markdown,
            "sections": sections,
        }
    except Exception as e:
        _reports[task_id] = {
            "status": "error",
            "markdown": None,
            "sections": [],
            "error": str(e),
        }


def _parse_sections(markdown: str) -> list[dict]:
    """Parse a markdown report into sections by ## headings."""
    sections = []
    current_title = None
    current_lines = []

    for line in markdown.split("\n"):
        if line.startswith("## "):
            # Save previous section
            if current_title is not None:
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_lines).strip(),
                })
            current_title = line[3:].strip()
            current_lines = []
        elif line.startswith("# ") and current_title is None:
            # Top-level heading (report title), skip
            continue
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_title is not None:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_lines).strip(),
        })

    return sections
