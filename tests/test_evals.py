from __future__ import annotations

from pathlib import Path

import pytest

from evals.summarize import load_runs, load_task_ids, summarize


ROOT = Path(__file__).resolve().parents[1]


def test_example_dogfood_results_cover_paired_tasks_and_pass() -> None:
    report = summarize(
        load_runs(ROOT / "evals" / "example-results.jsonl"),
        load_task_ids(ROOT / "evals" / "tasks.json"),
    )

    assert report["passes"] is True
    assert report["groups"]["C"]["reuse_rate"] == 1.0


def test_dogfood_summary_rejects_unpaired_task_groups() -> None:
    shared = {
        "correctness": 1.0,
        "evidence_seconds": 10,
        "investigation_commands": 1,
        "context_units": 100,
        "context_unit": "tokens",
        "stale_memory_misuses": 0,
        "maintenance_seconds": 0,
        "used_memory_ids": [],
    }
    runs = [
        shared | {"run_id": "hard-A", "task_id": "hard", "group": "A"},
        shared | {"run_id": "hard-B", "task_id": "hard", "group": "B"},
        shared | {"run_id": "easy-C", "task_id": "easy", "group": "C"},
    ]

    with pytest.raises(ValueError, match="equal paired A/B/C runs"):
        summarize(runs, {"hard", "easy"})
