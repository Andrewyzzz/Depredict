"""
Checkpoint system for incremental persistence of debate pipeline stages.
Inspired by MiroFish's ReportManager incremental storage pattern.
"""

import json
import os
from glob import glob
from pathlib import Path


class CheckpointManager:
    """Saves and loads intermediate results for a single debate task.

    Directory layout under task_dir/:
        round_1.json
        round_2.json
        round_3.json
        meta_predictions.json
        aggregation.json
        section_00.md
        section_01.md
        ...
    """

    # Ordered list of stages for resume-point detection
    _STAGE_ORDER = [
        "round_1",
        "round_2",
        "round_3",
        "meta_predictions",
        "aggregation",
        "report",
    ]

    def __init__(self, task_dir: str):
        self.task_dir = task_dir
        os.makedirs(self.task_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Round results
    # ------------------------------------------------------------------

    def save_round(self, round_num: int, results: list) -> None:
        path = os.path.join(self.task_dir, f"round_{round_num}.json")
        with open(path, "w") as f:
            json.dump(results, f, indent=2)

    def load_round(self, round_num: int) -> list | None:
        path = os.path.join(self.task_dir, f"round_{round_num}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Meta-predictions
    # ------------------------------------------------------------------

    def save_meta_predictions(self, meta: dict) -> None:
        path = os.path.join(self.task_dir, "meta_predictions.json")
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)

    def load_meta_predictions(self) -> dict | None:
        path = os.path.join(self.task_dir, "meta_predictions.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def save_aggregation(self, agg: dict) -> None:
        path = os.path.join(self.task_dir, "aggregation.json")
        with open(path, "w") as f:
            json.dump(agg, f, indent=2)

    def load_aggregation(self) -> dict | None:
        path = os.path.join(self.task_dir, "aggregation.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Report sections
    # ------------------------------------------------------------------

    def save_report_section(self, idx: int, content: str) -> None:
        path = os.path.join(self.task_dir, f"section_{idx:02d}.md")
        with open(path, "w") as f:
            f.write(content)

    def load_report_sections(self) -> list[str]:
        """Load all saved report sections in order."""
        pattern = os.path.join(self.task_dir, "section_*.md")
        paths = sorted(glob(pattern))
        sections = []
        for p in paths:
            with open(p) as f:
                sections.append(f.read())
        return sections

    def assemble_report(self) -> str:
        """Combine all report sections into a single markdown document."""
        sections = self.load_report_sections()
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Resume helpers
    # ------------------------------------------------------------------

    def get_last_completed_stage(self) -> str:
        """Determine the last fully-completed stage by checking which
        checkpoint files exist on disk.

        Returns the stage name (e.g. "round_2") or "" if nothing saved.
        """
        last = ""
        for stage in self._STAGE_ORDER:
            if stage.startswith("round_"):
                path = os.path.join(self.task_dir, f"{stage}.json")
            elif stage == "meta_predictions":
                path = os.path.join(self.task_dir, "meta_predictions.json")
            elif stage == "aggregation":
                path = os.path.join(self.task_dir, "aggregation.json")
            elif stage == "report":
                # Report is considered complete if at least one section exists
                pattern = os.path.join(self.task_dir, "section_*.md")
                if glob(pattern):
                    last = stage
                continue
            else:
                continue

            if os.path.exists(path):
                last = stage
        return last

    def has_checkpoint(self) -> bool:
        """Return True if any checkpoint data exists for this task."""
        return self.get_last_completed_stage() != ""
