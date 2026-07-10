from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from evals.summarize import load_runs, load_task_ids, validate_run
except ModuleNotFoundError:  # Support `python3 evals/record.py ...`.
    from summarize import load_runs, load_task_ids, validate_run


@contextlib.contextmanager
def _exclusive_lock(path: Path):
    """Hold an adjacent cross-process lock while checking and appending."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_run(results: Path, tasks: Path, run: dict[str, Any]) -> dict[str, Any]:
    """Validate one real run and append exactly one JSONL record."""

    normalized = validate_run(run)
    task_ids = load_task_ids(tasks)
    if normalized["task_id"] not in task_ids:
        raise ValueError(f"unknown task_id: {normalized['task_id']}")

    # Do not persist the compatibility-only v0.1 field in new records.
    normalized.pop("used_memory_ids", None)
    encoded = (json.dumps(normalized, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    lock_path = results.with_name(results.name + ".lock")
    with _exclusive_lock(lock_path):
        existing = []
        if results.exists() and results.stat().st_size:
            existing = load_runs(results)
        existing_run_ids = {item["run_id"] for item in existing}
        if normalized["run_id"] in existing_run_ids:
            raise ValueError(f"duplicate run_id: {normalized['run_id']}")
        existing_units = {item["context_unit"] for item in existing}
        if existing_units and normalized["context_unit"] not in existing_units:
            raise ValueError(
                "context_unit must match existing runs: "
                + ", ".join(sorted(existing_units))
            )

        with results.open("ab+") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) != b"\n":
                    handle.seek(0, os.SEEK_END)
                    handle.write(b"\n")
            handle.seek(0, os.SEEK_END)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append one completed MemoBox A/B/C dogfood run."
    )
    parser.add_argument("results", type=Path, help="JSONL results file to append")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).with_name("tasks.json"),
        help="Task definitions; task_id must already exist here.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--group", required=True, choices=("A", "B", "C"))
    parser.add_argument("--correctness", required=True, type=float)
    parser.add_argument("--evidence-seconds", required=True, type=float)
    parser.add_argument("--investigation-commands", required=True, type=int)
    parser.add_argument("--context-units", required=True, type=int)
    parser.add_argument("--context-unit", required=True)
    parser.add_argument("--stale-memory-misuses", required=True, type=int)
    parser.add_argument("--maintenance-seconds", required=True, type=float)
    parser.add_argument("--opened-memory-id", action="append", default=[])
    parser.add_argument("--reused-memory-id", action="append", default=[])
    parser.add_argument("--notes")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    run: dict[str, Any] = {
        "run_id": args.run_id,
        "task_id": args.task_id,
        "group": args.group,
        "correctness": args.correctness,
        "evidence_seconds": args.evidence_seconds,
        "investigation_commands": args.investigation_commands,
        "context_units": args.context_units,
        "context_unit": args.context_unit,
        "stale_memory_misuses": args.stale_memory_misuses,
        "maintenance_seconds": args.maintenance_seconds,
        "opened_memory_ids": args.opened_memory_id,
        "reused_memory_ids": args.reused_memory_id,
    }
    if args.notes is not None:
        run["notes"] = args.notes
    try:
        recorded = append_run(args.results, args.tasks, run)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json_output:
        print(json.dumps(recorded, ensure_ascii=False, sort_keys=True))
    else:
        print(f"recorded {recorded['run_id']} -> {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
