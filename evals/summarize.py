from __future__ import annotations

import argparse
import json
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
    "used_memory_ids",
}


def load_runs(path: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        missing = REQUIRED - value.keys()
        if missing:
            raise ValueError(f"line {line_number}: missing {', '.join(sorted(missing))}")
        if value["group"] not in GROUPS:
            raise ValueError(f"line {line_number}: group must be A, B, or C")
        if not 0 <= float(value["correctness"]) <= 1:
            raise ValueError(f"line {line_number}: correctness must be between 0 and 1")
        runs.append(value)
    if not runs:
        raise ValueError("results file contains no runs")
    return runs


def median(rows: list[dict[str, Any]], key: str) -> float:
    return float(statistics.median(float(row[key]) for row in rows))


def load_task_ids(path: Path) -> set[str]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError("tasks file must contain a JSON array")
    task_ids = {str(value["id"]) for value in values if isinstance(value, dict) and value.get("id")}
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
    for run in runs:
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
            "reuse_rate": sum(bool(row["used_memory_ids"]) for row in rows) / len(rows),
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
