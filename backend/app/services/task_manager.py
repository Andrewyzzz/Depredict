"""
Task state machine for managing debate prediction tasks.
Inspired by MiroFish's SimulationManager pattern.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class DebateStatus(str, Enum):
    CREATED = "CREATED"
    RETRIEVING = "RETRIEVING"
    EXTRACTING_ENTITIES = "EXTRACTING_ENTITIES"
    DEBATING_R1 = "DEBATING_R1"
    DEBATING_R2 = "DEBATING_R2"
    DEBATING_R3 = "DEBATING_R3"
    META_PREDICTING = "META_PREDICTING"
    AGGREGATING = "AGGREGATING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class DebateTaskState:
    task_id: str
    question: str
    market_price: float | None = None
    status: DebateStatus = DebateStatus.CREATED
    created_at: str = ""
    updated_at: str = ""
    error: str | None = None
    progress_percent: int = 0
    progress_message: str = ""
    current_stage: str = ""
    agents_completed: int = 0
    total_agents: int = 10
    round1_results: list | None = None
    round2_results: list | None = None
    round3_results: list | None = None
    meta_predictions: dict | None = None
    aggregation_results: dict | None = None
    entities: dict | None = None
    report: str | None = None
    rag_sources: list | None = None
    raft_metrics: dict | None = None
    result: dict | None = None

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        """Full serialization including all results data."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_simple_dict(self) -> dict:
        """Lightweight serialization for progress updates / list views.
        Excludes large result payloads."""
        return {
            "task_id": self.task_id,
            "question": self.question,
            "market_price": self.market_price,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "current_stage": self.current_stage,
            "agents_completed": self.agents_completed,
            "total_agents": self.total_agents,
        }


class TaskManager:
    """Manages lifecycle and persistence of debate prediction tasks."""

    TASK_DATA_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "data", "tasks",
    )

    def __init__(self):
        self._tasks: dict[str, DebateTaskState] = {}
        self._progress_callback: Callable[[str, dict], None] | None = None
        # Normalise the path and ensure directory exists
        self.TASK_DATA_DIR = os.path.normpath(self.TASK_DATA_DIR)
        os.makedirs(self.TASK_DATA_DIR, exist_ok=True)
        # Load any existing tasks from disk into cache
        self._load_all_tasks()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task(self, question: str, market_price: float | None = None) -> DebateTaskState:
        """Create a new debate task and persist it."""
        task_id = str(uuid.uuid4())
        state = DebateTaskState(
            task_id=task_id,
            question=question,
            market_price=market_price,
            status=DebateStatus.CREATED,
            progress_message="Task created",
            current_stage="created",
        )
        self._tasks[task_id] = state
        self._save_task_state(state)
        return state

    def get_task(self, task_id: str) -> DebateTaskState | None:
        """Return a task by id, checking cache then disk."""
        if task_id in self._tasks:
            return self._tasks[task_id]
        return self._load_task_state(task_id)

    def list_tasks(self) -> list[DebateTaskState]:
        """Return all known tasks, sorted by creation time descending."""
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )

    def update_progress(
        self,
        task_id: str,
        stage: str,
        percent: int,
        message: str,
        **kwargs: Any,
    ) -> DebateTaskState | None:
        """Update task progress, persist, and fire callback.

        Keyword arguments can include:
            agents_completed (int)
            status (DebateStatus)
            error (str)
            data (dict) – partial results keyed by field name,
                e.g. data={"round1_results": [...]}
        """
        state = self.get_task(task_id)
        if state is None:
            return None

        state.current_stage = stage
        state.progress_percent = max(0, min(percent, 100))
        state.progress_message = message
        state.updated_at = datetime.now(timezone.utc).isoformat()

        # Map stage names to DebateStatus if not explicitly provided
        if "status" in kwargs:
            state.status = kwargs.pop("status")
        else:
            stage_status_map = {
                "retrieving": DebateStatus.RETRIEVING,
                "extracting_entities": DebateStatus.EXTRACTING_ENTITIES,
                "debating_r1": DebateStatus.DEBATING_R1,
                "debating_r2": DebateStatus.DEBATING_R2,
                "debating_r3": DebateStatus.DEBATING_R3,
                "meta_predicting": DebateStatus.META_PREDICTING,
                "aggregating": DebateStatus.AGGREGATING,
                "generating_report": DebateStatus.GENERATING_REPORT,
                "completed": DebateStatus.COMPLETED,
                "failed": DebateStatus.FAILED,
            }
            if stage in stage_status_map:
                state.status = stage_status_map[stage]

        if "agents_completed" in kwargs:
            state.agents_completed = kwargs.pop("agents_completed")

        if "error" in kwargs:
            state.error = kwargs.pop("error")

        # Merge partial result data onto the state
        data: dict | None = kwargs.pop("data", None)
        if data:
            for key, value in data.items():
                if hasattr(state, key):
                    setattr(state, key, value)

        self._save_task_state(state)

        # Fire progress callback
        if self._progress_callback is not None:
            try:
                self._progress_callback(task_id, state.to_simple_dict())
            except Exception:
                pass  # Don't let callback errors break the pipeline

        return state

    def set_progress_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Set a callback invoked on every progress update.

        callback signature: callback(task_id: str, state_dict: dict)
        """
        self._progress_callback = callback

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _task_file(self, task_id: str) -> str:
        return os.path.join(self.TASK_DATA_DIR, f"{task_id}.json")

    def _save_task_state(self, state: DebateTaskState) -> None:
        path = self._task_file(state.task_id)
        with open(path, "w") as f:
            json.dump(state.to_dict(), f, indent=2)

    def _load_task_state(self, task_id: str) -> DebateTaskState | None:
        path = self._task_file(task_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        data["status"] = DebateStatus(data["status"])
        state = DebateTaskState(**data)
        self._tasks[task_id] = state
        return state

    def _load_all_tasks(self) -> None:
        """Load every persisted task into the in-memory cache."""
        if not os.path.isdir(self.TASK_DATA_DIR):
            return
        for filename in os.listdir(self.TASK_DATA_DIR):
            if filename.endswith(".json"):
                task_id = filename[:-5]
                if task_id not in self._tasks:
                    self._load_task_state(task_id)
