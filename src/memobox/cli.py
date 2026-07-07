from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from memobox.models import Artifact, MemoryMail, SourceRef, VALID_STATUSES
from memobox.store import JsonMemoBoxStore

MEMORY_POLICY = [
    "MemoBox is a model-readable memory store, not a relevance or orchestration engine.",
    "The index contains subjects, summaries, tags, status, timestamps, and body/evidence locations.",
    "The model decides whether to call MemoBox, which ids to read, and whether evidence is needed.",
    "Trace records are exposed only through an explicit trace read.",
    "Do not treat directory order or pagination as relevance decisions.",
]
MEMORY_STRUCTURE = {
    "index": {
        "file": "index.json",
        "contains": [
            "id",
            "subject",
            "summary",
            "project",
            "workspace",
            "team",
            "role",
            "tags",
            "participants",
            "importance",
            "status",
            "confidence",
            "created_at",
            "updated_at",
        ],
        "does_not_contain": ["context", "decisions", "raw_trace", "full evidence"],
    },
    "mail_body": {
        "path_template": "mails/<id>.json",
        "open_with": "memobox --store <store> read <id> --json",
        "contains": ["context", "decisions", "artifacts", "next_actions", "risks", "source_refs"],
    },
    "raw_trace": {
        "path_template": "traces/<id>.jsonl",
        "open_with": "memobox --store <store> trace <id> --json",
        "contains": ["optional raw conversation, tool, terminal, or external evidence events"],
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = JsonMemoBoxStore(args.store)

    try:
        if args.command == "init":
            store.initialize()
            print(f"initialized {store.root}")
            return 0
        if args.command in {"add", "write"}:
            return cmd_write(store, args)
        if args.command in {"inbox", "map", "index"}:
            return cmd_index(store, args)
        if args.command in {"show", "read"}:
            return cmd_read(store, args)
        if args.command == "status":
            return cmd_status(store, args)
        if args.command in {"raw", "trace"}:
            return cmd_trace(store, args)
        if args.command == "recall":
            return cmd_recall(store, args)
        if args.command == "remember":
            return cmd_remember(store, args)
        if args.command == "promote":
            return cmd_promote(store, args)
        if args.command == "curate":
            return cmd_curate(store, args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memobox", description="MemoBox")
    parser.add_argument("--store", default=".memobox", help="MemoBox storage directory.")
    public_commands = "{init,write,index,read,status,trace,promote,curate}"
    subparsers = parser.add_subparsers(dest="command", required=True, metavar=public_commands)

    subparsers.add_parser("init", help="Initialize a memobox store.")

    write = subparsers.add_parser("write", help="Write one Memory Mail record.")
    add_write_arguments(write)

    add = add_hidden_parser(subparsers, "add")
    add_write_arguments(add)

    add_index_parser(subparsers, "index", "List memory index records without judging relevance.")
    add_index_parser(subparsers, "inbox", argparse.SUPPRESS, hidden=True)
    add_index_parser(subparsers, "map", argparse.SUPPRESS, hidden=True)

    read = subparsers.add_parser("read", help="Read one Memory Mail body.")
    read.add_argument("id")
    read.add_argument("--json", action="store_true")

    show = add_hidden_parser(subparsers, "show")
    show.add_argument("id")
    show.add_argument("--raw", action="store_true", help=argparse.SUPPRESS)
    show.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="Update memory mail status.")
    status.add_argument("id")
    status.add_argument("status", choices=sorted(VALID_STATUSES))
    status.add_argument("--json", action="store_true")

    trace = subparsers.add_parser("trace", help="Read raw trace evidence for one memory.")
    trace.add_argument("id")
    trace.add_argument("--json", action="store_true")

    raw = add_hidden_parser(subparsers, "raw")
    raw.add_argument("id")
    raw.add_argument("--json", action="store_true")

    recall = add_hidden_parser(subparsers, "recall")
    recall.add_argument("task", nargs="?", default="", help="Optional task text; never used to filter memories.")
    recall.add_argument("--project", help="Optional task metadata for the model; not used as a filter.")
    recall.add_argument("--workspace", help="Optional task metadata for the model; not used as a filter.")
    recall.add_argument("--team", help="Optional task metadata for the model; not used as a filter.")
    recall.add_argument("--role", help="Optional task metadata for the model; not used as a filter.")
    recall.add_argument("--global-store", default=default_global_store())
    recall.add_argument("--page", type=int, default=1, help="Directory page to print.")
    recall.add_argument("--per-page", type=int, default=200, help="Entries per store page.")
    recall.add_argument("--project-limit", type=int, help=argparse.SUPPRESS)
    recall.add_argument("--global-limit", type=int, help=argparse.SUPPRESS)
    recall.add_argument("--all-statuses", action="store_true", help=argparse.SUPPRESS)
    recall.add_argument("--json", action="store_true")

    remember = add_hidden_parser(subparsers, "remember")
    remember.add_argument("--subject", required=True)
    remember.add_argument("--summary", required=True)
    remember.add_argument("--project", required=True)
    remember.add_argument("--workspace", default="")
    remember.add_argument("--team", default="")
    remember.add_argument("--role", default="memory-curator")
    remember.add_argument("--tags", default="", help="Comma-separated tags.")
    remember.add_argument("--participants", default="", help="Comma-separated participants.")
    remember.add_argument("--importance", default="normal", choices=["low", "normal", "high", "critical"])
    remember.add_argument("--confidence", type=float, default=1.0)
    remember.add_argument("--body", default="", help="Task outcome, rationale, and useful context.")
    remember.add_argument("--body-file", default="")
    remember.add_argument("--decision", action="append", default=[])
    remember.add_argument("--next-action", action="append", default=[])
    remember.add_argument("--risk", action="append", default=[])
    remember.add_argument("--artifact", action="append", default=[], help="KIND:URI")
    remember.add_argument("--source-ref", action="append", default=[], help="KIND:REF")
    remember.add_argument("--raw-trace-file", default="")
    remember.add_argument("--json", action="store_true")

    promote = subparsers.add_parser("promote", help="Copy one reusable memory into a global MemoBox store.")
    promote.add_argument("id")
    promote.add_argument("--global-store", default=default_global_store())
    promote.add_argument("--target-project", default="global")
    promote.add_argument("--tag", action="append", default=[], help="Extra tag for promoted memory.")
    promote.add_argument("--with-raw", action="store_true", help="Also copy raw trace.")
    promote.add_argument("--archive-source", action="store_true", help="Archive the source project memory after promotion.")
    promote.add_argument("--json", action="store_true")

    curate = subparsers.add_parser("curate", help="Maintain memory records: find duplicates, merge, mark stale, or pin.")
    curate_subparsers = curate.add_subparsers(dest="curate_command", required=True)

    duplicates = curate_subparsers.add_parser("duplicates", help="List likely duplicate memories by project and subject.")
    duplicates.add_argument("--project")
    duplicates.add_argument("--json", action="store_true")

    merge = curate_subparsers.add_parser("merge", help="Merge several memory mails into one and archive the sources.")
    merge.add_argument("ids", nargs="+")
    merge.add_argument("--subject", required=True)
    merge.add_argument("--summary", required=True)
    merge.add_argument("--project")
    merge.add_argument("--workspace")
    merge.add_argument("--team")
    merge.add_argument("--role", default="memory-curator")
    merge.add_argument("--tags", default="")
    merge.add_argument("--archive-sources", action=argparse.BooleanOptionalAction, default=True)
    merge.add_argument("--json", action="store_true")

    stale = curate_subparsers.add_parser("stale", help="Mark exact memory ids as stale.")
    stale.add_argument("ids", nargs="+")
    stale.add_argument("--project", help=argparse.SUPPRESS)
    stale.add_argument("--limit", type=int, help=argparse.SUPPRESS)
    stale.add_argument("--json", action="store_true")

    pin = curate_subparsers.add_parser("pin", help="Pin exact memory ids.")
    pin.add_argument("ids", nargs="+")
    pin.add_argument("--project", help=argparse.SUPPRESS)
    pin.add_argument("--limit", type=int, help=argparse.SUPPRESS)
    pin.add_argument("--json", action="store_true")

    return parser


def add_write_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subject", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--project", default="")
    parser.add_argument("--workspace", default="")
    parser.add_argument("--team", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--tags", default="", help="Comma-separated tags.")
    parser.add_argument("--participants", default="", help="Comma-separated participants.")
    parser.add_argument("--importance", default="normal", choices=["low", "normal", "high", "critical"])
    parser.add_argument("--status", default="inbox", choices=sorted(VALID_STATUSES))
    parser.add_argument("--confidence", type=float, default=1.0)
    parser.add_argument("--body", default="", help="Expandable memory body/context.")
    parser.add_argument("--body-file", default="", help="Read expandable memory body from file.")
    parser.add_argument("--decision", action="append", default=[])
    parser.add_argument("--next-action", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--artifact", action="append", default=[], help="KIND:URI")
    parser.add_argument("--source-ref", action="append", default=[], help="KIND:REF")
    parser.add_argument("--raw-trace-file", default="", help="JSONL or text file to attach as raw trace.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")


def add_hidden_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name)
    subparsers._choices_actions = [  # type: ignore[attr-defined]
        action for action in subparsers._choices_actions if action.dest != name  # type: ignore[attr-defined]
    ]
    return parser


def add_index_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    *,
    hidden: bool = False,
) -> None:
    index = add_hidden_parser(subparsers, name) if hidden else subparsers.add_parser(name, help=help_text)
    index.add_argument("--global-store", help="Also list a global MemoBox store when explicitly provided.")
    index.add_argument("--page", type=int, default=1, help="Directory page to print.")
    index.add_argument("--per-page", type=int, default=200, help="Entries per page.")
    index.add_argument("--json", action="store_true")


def cmd_write(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
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


def cmd_index(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    global_store_path = getattr(args, "global_store", None)
    if global_store_path:
        global_store = JsonMemoBoxStore(Path(global_store_path).expanduser())
        payload: dict[str, Any] = {
            "policy": MEMORY_POLICY,
            "structure": MEMORY_STRUCTURE,
            "stores": [
                build_index_payload("project", store, page=args.page, per_page=args.per_page),
                build_index_payload("global", global_store, page=args.page, per_page=args.per_page),
            ],
        }
    else:
        payload = build_index_payload("project", store, page=args.page, per_page=args.per_page)
    if args.json:
        print_json(payload)
    else:
        if "stores" in payload:
            for store_payload in payload["stores"]:
                print_index_payload(store_payload)
        else:
            print_index_payload(payload)
    return 0


def cmd_read(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    mail = store.open_mail(args.id)
    payload: dict[str, Any] = mail.to_dict()
    if getattr(args, "raw", False):
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
        if getattr(args, "raw", False):
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


def cmd_trace(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    trace = store.open_raw_trace(args.id)
    if args.json:
        print_json(trace)
    else:
        for event in trace:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_recall(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    global_store = JsonMemoBoxStore(Path(args.global_store).expanduser())
    payload = {
        "task": args.task,
        "task_metadata": {
            "project": args.project or "",
            "workspace": args.workspace or "",
            "team": args.team or "",
            "role": args.role or "",
        },
        "policy": MEMORY_POLICY,
        "structure": MEMORY_STRUCTURE,
        "stores": [
            build_index_payload("project", store, page=args.page, per_page=args.per_page),
            build_index_payload("global", global_store, page=args.page, per_page=args.per_page),
        ],
    }
    if args.json:
        print_json(payload)
    else:
        if args.task:
            print(f"task: {args.task}")
        for store_payload in payload["stores"]:
            print_index_payload(store_payload)
    return 0


def cmd_remember(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    tags = ["task-memory", *parse_csv(args.tags)]
    mail = MemoryMail(
        id="",
        subject=args.subject,
        summary=args.summary,
        project=args.project,
        workspace=args.workspace,
        team=args.team,
        role=args.role,
        tags=dedupe(tags),
        participants=parse_csv(args.participants),
        importance=args.importance,
        status="inbox",
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


def cmd_promote(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    source = store.open_mail(args.id)
    global_store = JsonMemoBoxStore(Path(args.global_store).expanduser())
    tags = dedupe([*source.tags, "promoted", *args.tag])
    source_refs = [
        *source.source_refs,
        SourceRef(kind="memobox", ref=f"{store.root}:{source.id}", note="promoted from project memory"),
    ]
    promoted = MemoryMail(
        id="",
        subject=source.subject,
        summary=source.summary,
        project=args.target_project,
        workspace="",
        team=source.team,
        role=source.role,
        tags=tags,
        participants=list(source.participants),
        importance=source.importance,
        status="inbox",
        confidence=source.confidence,
        context=source.context,
        decisions=list(source.decisions),
        artifacts=list(source.artifacts),
        next_actions=list(source.next_actions),
        risks=list(source.risks),
        source_refs=source_refs,
    )
    raw_trace = store.open_raw_trace(source.id) if args.with_raw else None
    stored = global_store.add_mail(promoted, raw_trace=raw_trace)
    if args.archive_source:
        store.update_status(source.id, "archived")
    payload = {
        "source_id": source.id,
        "promoted_id": stored.id,
        "project_store": str(store.root),
        "global_store": str(global_store.root),
        "archived_source": bool(args.archive_source),
    }
    if args.json:
        print_json(payload)
    else:
        print(f"{source.id}\t->\t{stored.id}")
    return 0


def cmd_curate(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    if args.curate_command == "duplicates":
        return cmd_curate_duplicates(store, args)
    if args.curate_command == "merge":
        return cmd_curate_merge(store, args)
    if args.curate_command == "stale":
        return cmd_curate_status(store, args, "stale")
    if args.curate_command == "pin":
        return cmd_curate_status(store, args, "pinned")
    raise ValueError(f"Unsupported curate command: {args.curate_command}")


def cmd_curate_duplicates(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in store.list_index():
        if args.project and entry.project != args.project:
            continue
        key = f"{entry.project}:{normalize_duplicate_key(entry.subject)}"
        groups[key].append(entry.to_dict())
    duplicates = [
        {"key": key, "entries": entries}
        for key, entries in sorted(groups.items())
        if len(entries) > 1
    ]
    if args.json:
        print_json(duplicates)
    else:
        for group in duplicates:
            print(group["key"])
            for entry in group["entries"]:
                print(f"  {entry['id']}\t{entry['status']}\t{entry['subject']}")
    return 0


def cmd_curate_merge(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    mails = [store.open_mail(mail_id) for mail_id in args.ids]
    first = mails[0]
    merged = MemoryMail(
        id="",
        subject=args.subject,
        summary=args.summary,
        project=args.project if args.project is not None else first.project,
        workspace=args.workspace if args.workspace is not None else first.workspace,
        team=args.team if args.team is not None else first.team,
        role=args.role,
        tags=dedupe([*parse_csv(args.tags), *(tag for mail in mails for tag in mail.tags), "merged"]),
        participants=dedupe(participant for mail in mails for participant in mail.participants),
        importance=max((mail.importance for mail in mails), key=importance_rank),
        status="inbox",
        confidence=min(mail.confidence for mail in mails),
        context=merge_sections("Memory", [(mail.id, mail.context) for mail in mails]),
        decisions=dedupe(decision for mail in mails for decision in mail.decisions),
        artifacts=[artifact for mail in mails for artifact in mail.artifacts],
        next_actions=dedupe(action for mail in mails for action in mail.next_actions),
        risks=dedupe(risk for mail in mails for risk in mail.risks),
        source_refs=[
            *(source_ref for mail in mails for source_ref in mail.source_refs),
            *(SourceRef(kind="memobox", ref=mail.id, note="merged source") for mail in mails),
        ],
    )
    stored = store.add_mail(merged)
    if args.archive_sources:
        for mail in mails:
            store.update_status(mail.id, "archived")
    if args.json:
        print_json(
            {
                "merged_id": stored.id,
                "source_ids": [mail.id for mail in mails],
                "archived_sources": bool(args.archive_sources),
            }
        )
    else:
        print(stored.id)
    return 0


def cmd_curate_status(store: JsonMemoBoxStore, args: argparse.Namespace, status: str) -> int:
    updated = [store.update_status(mail_id, status).to_index_entry().to_dict() for mail_id in args.ids]
    if args.json:
        print_json(updated)
    else:
        for entry in updated:
            print(f"{entry['id']}\t{entry['status']}\t{entry['subject']}")
    return 0


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def default_global_store() -> str:
    return os.environ.get("MEMOBOX_GLOBAL_STORE", "~/.memobox-global")


def dedupe(items: Any) -> list[Any]:
    result: list[Any] = []
    seen: set[Any] = set()
    for item in items:
        key = item if isinstance(item, (str, int, float, bool, tuple)) else repr(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


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


def build_index_payload(scope: str, store: JsonMemoBoxStore, *, page: int, per_page: int) -> dict[str, Any]:
    page = max(1, page)
    per_page = max(1, per_page)
    entries = store.list_index()
    total = len(entries)
    start = (page - 1) * per_page
    stop = start + per_page
    page_entries = entries[start:stop]
    return {
        "scope": scope,
        "store": str(store.root),
        "policy": MEMORY_POLICY,
        "structure": MEMORY_STRUCTURE,
        "total_entries": total,
        "page": page,
        "per_page": per_page,
        "has_previous": page > 1 and total > 0,
        "has_next": stop < total,
        "entries": [format_directory_entry(store, entry) for entry in page_entries],
    }


def format_directory_entry(store: JsonMemoBoxStore, entry: Any) -> dict[str, Any]:
    payload = entry.to_dict()
    mail_path = store.mail_path(entry.id)
    raw_trace_path = store.trace_path(entry.id)
    payload["mail_body"] = {
        "path": str(mail_path),
        "exists": mail_path.exists(),
        "open_command": f"memobox --store {store.root} read {entry.id} --json",
    }
    payload["raw_trace"] = {
        "path": str(raw_trace_path),
        "exists": raw_trace_path.exists(),
        "open_command": f"memobox --store {store.root} trace {entry.id} --json",
    }
    return payload


def print_index_payload(payload: dict[str, Any]) -> None:
    print(
        f"# MemoBox {payload['scope']} index: {payload['total_entries']} entries "
        f"(page {payload['page']}, per_page {payload['per_page']})"
    )
    print("Policy: MemoBox exposes storage structure; the model decides whether and what to read.")
    for entry in payload["entries"]:
        tags = ",".join(entry["tags"])
        print(f"{entry['id']}\t{entry['status']}\t{entry['project']}\t{tags}\t{entry['subject']}")
        print(f"  {entry['summary']}")
        print(f"  body: {entry['mail_body']['path']}")
        print(f"  raw: {entry['raw_trace']['path']}")
    if payload["has_next"]:
        next_page = payload["page"] + 1
        print(f"More entries are available on page {next_page}.")


def normalize_duplicate_key(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def importance_rank(value: str) -> int:
    return {"low": 0, "normal": 1, "high": 2, "critical": 3}.get(value, 1)


def merge_sections(title: str, sections: list[tuple[str, str]]) -> str:
    lines = [f"# Merged {title}"]
    for mail_id, body in sections:
        if not body:
            continue
        lines.extend(["", f"## Source: {mail_id}", body])
    return "\n".join(lines).strip()


if __name__ == "__main__":
    raise SystemExit(main())
