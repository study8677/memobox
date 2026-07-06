from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from memobox.models import Artifact, MemoryMail, SourceRef, VALID_STATUSES
from memobox.search import DEFAULT_ACTIVE_STATUSES, MemoBoxSearcher
from memobox.store import JsonMemoBoxStore


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = JsonMemoBoxStore(args.store)

    try:
        if args.command == "init":
            store.initialize()
            print(f"initialized {store.root}")
            return 0
        if args.command == "add":
            return cmd_add(store, args)
        if args.command == "search":
            return cmd_search(store, args)
        if args.command == "show":
            return cmd_show(store, args)
        if args.command == "status":
            return cmd_status(store, args)
        if args.command == "raw":
            return cmd_raw(store, args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memobox", description="MemoBox")
    parser.add_argument("--store", default=".memobox", help="MemoBox storage directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize a memobox store.")

    add = subparsers.add_parser("add", help="Add one task-level memory mail.")
    add.add_argument("--subject", required=True)
    add.add_argument("--summary", required=True)
    add.add_argument("--project", default="")
    add.add_argument("--workspace", default="")
    add.add_argument("--team", default="")
    add.add_argument("--role", default="")
    add.add_argument("--tags", default="", help="Comma-separated tags.")
    add.add_argument("--participants", default="", help="Comma-separated participants.")
    add.add_argument("--importance", default="normal", choices=["low", "normal", "high", "critical"])
    add.add_argument("--status", default="inbox", choices=sorted(VALID_STATUSES))
    add.add_argument("--confidence", type=float, default=1.0)
    add.add_argument("--body", default="", help="Expandable memory body/context.")
    add.add_argument("--body-file", default="", help="Read expandable memory body from file.")
    add.add_argument("--decision", action="append", default=[])
    add.add_argument("--next-action", action="append", default=[])
    add.add_argument("--risk", action="append", default=[])
    add.add_argument("--artifact", action="append", default=[], help="KIND:URI")
    add.add_argument("--source-ref", action="append", default=[], help="KIND:REF")
    add.add_argument("--raw-trace-file", default="", help="JSONL or text file to attach as raw trace.")
    add.add_argument("--json", action="store_true", help="Print JSON.")

    search = subparsers.add_parser("search", help="Search lightweight index only.")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--project")
    search.add_argument("--workspace")
    search.add_argument("--team")
    search.add_argument("--role")
    search.add_argument(
        "--status",
        action="append",
        choices=sorted(VALID_STATUSES),
        help="Repeat to include specific statuses. Defaults to inbox/pinned/needs_review.",
    )
    search.add_argument("--all-statuses", action="store_true")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--json", action="store_true")

    show = subparsers.add_parser("show", help="Open one memory mail body.")
    show.add_argument("id")
    show.add_argument("--raw", action="store_true", help="Also include raw trace.")
    show.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="Update memory mail status.")
    status.add_argument("id")
    status.add_argument("status", choices=sorted(VALID_STATUSES))
    status.add_argument("--json", action="store_true")

    raw = subparsers.add_parser("raw", help="Open raw trace explicitly.")
    raw.add_argument("id")
    raw.add_argument("--json", action="store_true")

    return parser


def cmd_add(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    mail = MemoryMail(
        id="",
        subject=args.subject,
        summary=args.summary,
        project=args.project,
        workspace=args.workspace,
        team=args.team,
        role=args.role,
        tags=parse_csv(args.tags),
        participants=parse_csv(args.participants),
        importance=args.importance,
        status=args.status,
        confidence=args.confidence,
        context=body,
        decisions=args.decision,
        artifacts=[parse_artifact(item) for item in args.artifact],
        next_actions=args.next_action,
        risks=args.risk,
        source_refs=[parse_source_ref(item) for item in args.source_ref],
    )
    raw_trace = read_raw_trace(args.raw_trace_file) if args.raw_trace_file else None
    stored = store.add_mail(mail, raw_trace=raw_trace)
    if args.json:
        print_json(stored.to_dict())
    else:
        print(stored.id)
    return 0


def cmd_search(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    statuses = None if args.all_statuses else tuple(args.status) if args.status else DEFAULT_ACTIVE_STATUSES
    results = MemoBoxSearcher(store).search(
        args.query,
        project=args.project,
        workspace=args.workspace,
        team=args.team,
        role=args.role,
        statuses=statuses,
        limit=args.limit,
    )
    if args.json:
        print_json(
            [
                {
                    "score": result.score,
                    "matched_terms": result.matched_terms,
                    "entry": result.entry.to_dict(),
                }
                for result in results
            ]
        )
    else:
        for result in results:
            entry = result.entry
            tags = ",".join(entry.tags)
            print(f"{entry.id}\t{result.score:.2f}\t{entry.status}\t{entry.project}\t{tags}\t{entry.subject}")
            print(f"  {entry.summary}")
    return 0


def cmd_show(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    mail = store.open_mail(args.id)
    payload: dict[str, Any] = mail.to_dict()
    if args.raw:
        payload["raw_trace"] = store.open_raw_trace(args.id)
    if args.json:
        print_json(payload)
    else:
        print(f"# {mail.subject}")
        print(f"id: {mail.id}")
        print(f"status: {mail.status}")
        print(f"project: {mail.project}")
        print(f"tags: {', '.join(mail.tags)}")
        print()
        print(mail.summary)
        if mail.context:
            print()
            print(mail.context)
        if mail.decisions:
            print("\nDecisions:")
            for decision in mail.decisions:
                print(f"- {decision}")
        if mail.next_actions:
            print("\nNext actions:")
            for action in mail.next_actions:
                print(f"- {action}")
        if args.raw:
            print("\nRaw trace:")
            for event in payload["raw_trace"]:
                print(json.dumps(event, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_status(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    mail = store.update_status(args.id, args.status)
    if args.json:
        print_json(mail.to_index_entry().to_dict())
    else:
        print(f"{mail.id}\t{mail.status}")
    return 0


def cmd_raw(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    trace = store.open_raw_trace(args.id)
    if args.json:
        print_json(trace)
    else:
        for event in trace:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
    return 0


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_artifact(value: str) -> Artifact:
    parts = value.split(":", 1)
    if len(parts) < 2:
        raise ValueError(f"Artifact must be KIND:URI, got {value!r}")
    return Artifact(kind=parts[0], uri=parts[1])


def parse_source_ref(value: str) -> SourceRef:
    parts = value.split(":", 1)
    if len(parts) < 2:
        raise ValueError(f"Source ref must be KIND:REF, got {value!r}")
    return SourceRef(kind=parts[0], ref=parts[1])


def read_raw_trace(path: str) -> list[dict[str, Any] | str]:
    events: list[dict[str, Any] | str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            events.append(line)
        else:
            if isinstance(parsed, dict):
                events.append(parsed)
            else:
                events.append({"value": parsed})
    return events


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
