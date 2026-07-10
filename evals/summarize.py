from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


GROUPS = ("A", "B", "C")
REQUIRED = {
    "run_id",
    "task_id",
    "group",
    "correctness",
    "evidence_seconds",
    "investigation_commands",
    "context_units",
    "context_unit",
    "stale_memory_misuses",
    "maintenance_seconds",
}
OPTIONAL = {
    "notes",
    # `used_memory_ids` is the v0.1 fixture field. New runs distinguish bodies
    # opened from memories that materially changed the outcome.
    "used_memory_ids",
    "opened_memory_ids",
    "reused_memory_ids",
}
ALLOWED = REQUIRED | OPTIONAL


def _require_non_empty_string(value: Any, field: str, location: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location}: {field} must be a non-empty string")


def _require_number(
    value: Any,
    field: str,
    location: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location}: {field} must be a number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{location}: {field} must be finite")
    if float(value) < minimum or (maximum is not None and float(value) > maximum):
        bounds = (
            f"between {minimum:g} and {maximum:g}"
            if maximum is not None
            else f">= {minimum:g}"
        )
        raise ValueError(f"{location}: {field} must be {bounds}")


def _require_non_negative_integer(value: Any, field: str, location: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{location}: {field} must be a non-negative integer")


def _memory_ids(value: Any, field: str, location: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{location}: {field} must be an array")
    for item in value:
        _require_non_empty_string(item, f"{field} item", location)
    if len(set(value)) != len(value):
        raise ValueError(f"{location}: {field} must not contain duplicates")
    return list(value)


def validate_run(value: Any, *, location: str = "run") -> dict[str, Any]:
    """Strictly validate and normalize one run without third-party packages."""

    if not isinstance(value, dict):
        raise ValueError(f"{location}: run must be a JSON object")
    missing = REQUIRED - value.keys()
    if missing:
        raise ValueError(f"{location}: missing {', '.join(sorted(missing))}")
    unknown = value.keys() - ALLOWED
    if unknown:
        raise ValueError(f"{location}: unknown {', '.join(sorted(unknown))}")

    normalized = dict(value)
    for field in ("run_id", "task_id", "context_unit"):
        _require_non_empty_string(normalized[field], field, location)
    if normalized["group"] not in GROUPS:
        raise ValueError(f"{location}: group must be A, B, or C")
    _require_number(
        normalized["correctness"],
        "correctness",
        location,
        minimum=0,
        maximum=1,
    )
    for field in ("evidence_seconds", "maintenance_seconds"):
        _require_number(normalized[field], field, location, minimum=0)
    for field in (
        "investigation_commands",
        "context_units",
        "stale_memory_misuses",
    ):
        _require_non_negative_integer(normalized[field], field, location)
    if "notes" in normalized and not isinstance(normalized["notes"], str):
        raise ValueError(f"{location}: notes must be a string")

    has_new_memory_fields = bool(
        {"opened_memory_ids", "reused_memory_ids"} & normalized.keys()
    )
    if has_new_memory_fields:
        missing_memory_fields = {
            "opened_memory_ids",
            "reused_memory_ids",
        } - normalized.keys()
        if missing_memory_fields:
            raise ValueError(
                f"{location}: missing {', '.join(sorted(missing_memory_fields))}"
            )
        opened = _memory_ids(
            normalized["opened_memory_ids"], "opened_memory_ids", location
        )
        reused = _memory_ids(
            normalized["reused_memory_ids"], "reused_memory_ids", location
        )
    elif "used_memory_ids" in normalized:
        # Preserve v0.1 example/results compatibility. Those runs did not
        # distinguish opening from material reuse, so the old field means both.
        reused = _memory_ids(
            normalized["used_memory_ids"], "used_memory_ids", location
        )
        opened = list(reused)
    else:
        raise ValueError(f"{location}: missing opened_memory_ids, reused_memory_ids")
    if "used_memory_ids" in normalized:
        used = _memory_ids(normalized["used_memory_ids"], "used_memory_ids", location)
        if has_new_memory_fields and used != reused:
            raise ValueError(f"{location}: used_memory_ids must equal reused_memory_ids")
    if not set(reused).issubset(opened):
        raise ValueError(
            f"{location}: reused_memory_ids must be a subset of opened_memory_ids"
        )
    normalized["opened_memory_ids"] = opened
    normalized["reused_memory_ids"] = reused

    if normalized["group"] in ("A", "B"):
        if opened or reused:
            raise ValueError(
                f"{location}: group {normalized['group']} cannot use MemoBox ids"
            )
        if normalized["maintenance_seconds"] != 0:
            raise ValueError(
                f"{location}: group {normalized['group']} maintenance_seconds must be 0"
            )
        if normalized["stale_memory_misuses"] != 0:
            raise ValueError(
                f"{location}: group {normalized['group']} stale_memory_misuses must be 0"
            )
    return normalized


def load_runs(path: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        runs.append(validate_run(value, location=f"line {line_number}"))
    if not runs:
        raise ValueError("results file contains no runs")
    return runs


def median(rows: list[dict[str, Any]], key: str) -> float:
    return float(statistics.median(float(row[key]) for row in rows))


def load_task_ids(path: Path) -> set[str]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError("tasks file must contain a JSON array")
    task_ids: set[str] = set()
    for index, value in enumerate(values, 1):
        if not isinstance(value, dict):
            raise ValueError(f"task {index} must be a JSON object")
        task_id = value.get("id")
        _require_non_empty_string(task_id, "id", f"task {index}")
        if task_id in task_ids:
            raise ValueError(f"duplicate task id: {task_id}")
        task_ids.add(task_id)
    if len(task_ids) != len(values):
        raise ValueError("every task must have one unique non-empty id")
    return task_ids


def summarize(runs: list[dict[str, Any]], expected_task_ids: set[str]) -> dict[str, Any]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_task: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    run_ids: set[str] = set()
    context_units: set[str] = set()
    for index, raw_run in enumerate(runs, 1):
        run = validate_run(raw_run, location=f"run {index}")
        if run["run_id"] in run_ids:
            raise ValueError(f"duplicate run_id: {run['run_id']}")
        run_ids.add(run["run_id"])
        context_units.add(str(run["context_unit"]))
        by_group[run["group"]].append(run)
        by_task[run["task_id"]][run["group"]].append(run)

    observed_task_ids = set(by_task)
    unknown_tasks = observed_task_ids - expected_task_ids
    missing_tasks = expected_task_ids - observed_task_ids
    if unknown_tasks:
        raise ValueError(f"unknown task ids: {', '.join(sorted(unknown_tasks))}")
    if missing_tasks:
        raise ValueError(f"missing task ids: {', '.join(sorted(missing_tasks))}")
    if len(context_units) != 1:
        raise ValueError("all runs must use the same context_unit")
    for task_id, task_groups in sorted(by_task.items()):
        counts = {group: len(task_groups[group]) for group in GROUPS}
        if not all(counts.values()) or len(set(counts.values())) != 1:
            raise ValueError(
                f"task {task_id!r} must have equal paired A/B/C runs; got {counts}"
            )

    missing_groups = [group for group in GROUPS if not by_group[group]]
    if missing_groups:
        raise ValueError(f"missing groups: {', '.join(missing_groups)}")

    metrics: dict[str, dict[str, Any]] = {}
    for group in GROUPS:
        rows = by_group[group]
        metrics[group] = {
            "runs": len(rows),
            "mean_correctness": statistics.fmean(float(row["correctness"]) for row in rows),
            "median_evidence_seconds": median(rows, "evidence_seconds"),
            "median_investigation_commands": median(rows, "investigation_commands"),
            "median_context_units": median(rows, "context_units"),
            "stale_memory_misuses": sum(int(row["stale_memory_misuses"]) for row in rows),
            "median_maintenance_seconds": median(rows, "maintenance_seconds"),
            "opened_rate": sum(bool(row["opened_memory_ids"]) for row in rows) / len(rows),
            "reuse_rate": sum(bool(row["reused_memory_ids"]) for row in rows) / len(rows),
        }

    best_time = min(metrics["A"]["median_evidence_seconds"], metrics["B"]["median_evidence_seconds"])
    best_commands = min(
        metrics["A"]["median_investigation_commands"],
        metrics["B"]["median_investigation_commands"],
    )
    best_correctness = max(metrics["A"]["mean_correctness"], metrics["B"]["mean_correctness"])
    c_metrics = metrics["C"]
    saved_seconds = max(0.0, best_time - c_metrics["median_evidence_seconds"])
    time_reduction = (saved_seconds / best_time * 100) if best_time else 0.0
    command_reduction = (
        (best_commands - c_metrics["median_investigation_commands"]) / best_commands * 100
        if best_commands
        else 0.0
    )
    maintenance_ratio = (
        c_metrics["median_maintenance_seconds"] / saved_seconds * 100 if saved_seconds else float("inf")
    )
    checks = {
        "evidence_time_reduction_at_least_25pct": time_reduction >= 25,
        "investigation_command_reduction_at_least_30pct": command_reduction >= 30,
        "correctness_no_regression": c_metrics["mean_correctness"] >= best_correctness,
        "zero_stale_memory_misuse": c_metrics["stale_memory_misuses"] == 0,
        "maintenance_below_20pct_of_saved_time": maintenance_ratio < 20,
    }
    return {
        "groups": metrics,
        "comparison": {
            "evidence_time_reduction_pct": time_reduction,
            "investigation_command_reduction_pct": command_reduction,
            "correctness_delta": c_metrics["mean_correctness"] - best_correctness,
            "maintenance_pct_of_saved_time": maintenance_ratio,
        },
        "checks": checks,
        "passes": all(checks.values()),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = []
    for group in GROUPS:
        item = report["groups"][group]
        lines.append(
            f"{group}: runs={item['runs']} correctness={item['mean_correctness']:.2f} "
            f"evidence={item['median_evidence_seconds']:.1f}s "
            f"commands={item['median_investigation_commands']:.1f} "
            f"opened={item['opened_rate']:.0%} "
            f"reuse={item['reuse_rate']:.0%}"
        )
    comparison = report["comparison"]
    lines.append(
        "C vs best A/B: "
        f"evidence={comparison['evidence_time_reduction_pct']:.1f}% faster, "
        f"commands={comparison['investigation_command_reduction_pct']:.1f}% fewer, "
        f"correctness_delta={comparison['correctness_delta']:+.2f}, "
        f"maintenance={comparison['maintenance_pct_of_saved_time']:.1f}% of saved time"
    )
    for name, passed in report["checks"].items():
        lines.append(f"{'PASS' if passed else 'FAIL'} {name}")
    lines.append(f"OVERALL {'PASS' if report['passes'] else 'FAIL'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize MemoBox A/B/C dogfood results.")
    parser.add_argument("results", type=Path)
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).with_name("tasks.json"),
        help="Task fixture file; every task must have equal paired A/B/C runs.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = summarize(load_runs(args.results), load_task_ids(args.tasks))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
