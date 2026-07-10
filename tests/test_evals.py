from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals.record import append_run
from evals.summarize import load_runs, load_task_ids, summarize, validate_run


ROOT = Path(__file__).resolve().parents[1]


def test_example_dogfood_results_cover_paired_tasks_and_pass() -> None:
    report = summarize(
        load_runs(ROOT / "evals" / "example-results.jsonl"),
        load_task_ids(ROOT / "evals" / "tasks.json"),
    )

    assert report["passes"] is True
    assert report["groups"]["C"]["reuse_rate"] == 1.0


def test_example_results_follow_current_run_schema_required_fields() -> None:
    schema = json.loads((ROOT / "evals" / "run.schema.json").read_text(encoding="utf-8"))
    required = set(schema["required"])
    raw_runs = [
        json.loads(line)
        for line in (ROOT / "evals" / "example-results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert raw_runs
    assert all(required <= run.keys() for run in raw_runs)


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


def test_append_run_records_opened_and_reused_ids(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text('[{"id":"real-task"}]', encoding="utf-8")
    results = tmp_path / "results.jsonl"
    run = {
        "run_id": "real-task-C-1",
        "task_id": "real-task",
        "group": "C",
        "correctness": 1.0,
        "evidence_seconds": 12.5,
        "investigation_commands": 2,
        "context_units": 300,
        "context_unit": "tokens",
        "stale_memory_misuses": 0,
        "maintenance_seconds": 1.5,
        "opened_memory_ids": ["opened", "reused"],
        "reused_memory_ids": ["reused"],
    }

    append_run(results, tasks, run)

    assert load_runs(results) == [run]


def test_append_run_rejects_unknown_task_without_writing(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text('[{"id":"known"}]', encoding="utf-8")
    results = tmp_path / "results.jsonl"
    run = {
        "run_id": "invented-C-1",
        "task_id": "invented",
        "group": "C",
        "correctness": 1.0,
        "evidence_seconds": 1,
        "investigation_commands": 1,
        "context_units": 1,
        "context_unit": "tokens",
        "stale_memory_misuses": 0,
        "maintenance_seconds": 0,
        "opened_memory_ids": [],
        "reused_memory_ids": [],
    }

    with pytest.raises(ValueError, match="unknown task_id"):
        append_run(results, tasks, run)

    assert not results.exists()


def test_concurrent_recorders_append_duplicate_run_only_once(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text('[{"id":"real-task"}]', encoding="utf-8")
    results = tmp_path / "results.jsonl"
    command = [
        sys.executable,
        str(ROOT / "evals" / "record.py"),
        str(results),
        "--tasks",
        str(tasks),
        "--run-id",
        "same-run",
        "--task-id",
        "real-task",
        "--group",
        "C",
        "--correctness",
        "1",
        "--evidence-seconds",
        "1",
        "--investigation-commands",
        "1",
        "--context-units",
        "1",
        "--context-unit",
        "tokens",
        "--stale-memory-misuses",
        "0",
        "--maintenance-seconds",
        "0",
    ]

    processes = [
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    completed = [process.communicate() + (process.returncode,) for process in processes]

    assert sorted(item[2] for item in completed) == [0, 2]
    assert len(load_runs(results)) == 1


def test_validate_run_rejects_reuse_that_was_not_opened() -> None:
    run = {
        "run_id": "task-C-1",
        "task_id": "task",
        "group": "C",
        "correctness": 1.0,
        "evidence_seconds": 1,
        "investigation_commands": 1,
        "context_units": 1,
        "context_unit": "tokens",
        "stale_memory_misuses": 0,
        "maintenance_seconds": 0,
        "opened_memory_ids": [],
        "reused_memory_ids": ["not-opened"],
    }

    with pytest.raises(ValueError, match="subset"):
        validate_run(run)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("investigation_commands", 1.5, "non-negative integer"),
        ("correctness", float("nan"), "finite"),
        ("unexpected", 1, "unknown unexpected"),
    ],
)
def test_validate_run_rejects_malformed_key_fields(
    field: str, value: object, message: str
) -> None:
    run = {
        "run_id": "task-A-1",
        "task_id": "task",
        "group": "A",
        "correctness": 1.0,
        "evidence_seconds": 1,
        "investigation_commands": 1,
        "context_units": 1,
        "context_unit": "tokens",
        "stale_memory_misuses": 0,
        "maintenance_seconds": 0,
        "opened_memory_ids": [],
        "reused_memory_ids": [],
    }
    run[field] = value

    with pytest.raises(ValueError, match=message):
        validate_run(run)


def test_validate_run_rejects_memobox_usage_in_baselines() -> None:
    run = {
        "run_id": "task-B-1",
        "task_id": "task",
        "group": "B",
        "correctness": 1.0,
        "evidence_seconds": 1,
        "investigation_commands": 1,
        "context_units": 1,
        "context_unit": "tokens",
        "stale_memory_misuses": 0,
        "maintenance_seconds": 0,
        "opened_memory_ids": ["memobox-id"],
        "reused_memory_ids": [],
    }

    with pytest.raises(ValueError, match="group B cannot use MemoBox ids"):
        validate_run(run)
