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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = JsonMemoBoxStore(args.store)

    try:
        if args.command == "init":
            store.initialize()
            print(f"initialized {store.root}")
            return 0
        if args.command == "write":
            return cmd_write(store, args)
        if args.command == "status":
            return cmd_status(store, args)
        if args.command == "promote":
            return cmd_promote(store, args)
        if args.command == "curate":
            return cmd_curate(store, args)
        if args.command == "verify":
            return cmd_verify(store, args)
        if args.command == "rebuild-index":
            return cmd_rebuild_index(store, args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memobox",
        description="MemoBox writes and maintains model-readable local memory files.",
        epilog=(
            "Read memory directly with Bash: cat .memobox/index.json, "
            "cat .memobox/mails/<id>.json, cat .memobox/traces/<id>.jsonl"
        ),
    )
    parser.add_argument("--store", default=".memobox", help="MemoBox storage directory.")
    public_commands = "{init,write,status,promote,curate,verify,rebuild-index}"
    subparsers = parser.add_subparsers(dest="command", required=True, metavar=public_commands)

    subparsers.add_parser("init", help="Initialize a memobox store.")

    write = subparsers.add_parser("write", help="Write one Memory Mail record.")
    add_write_arguments(write)

    status = subparsers.add_parser("status", help="Update memory mail status.")
    status.add_argument("id")
    status.add_argument("status", choices=sorted(VALID_STATUSES))
    status.add_argument("--json", action="store_true")

    promote = subparsers.add_parser("promote", help="Copy one reusable memory into a global MemoBox store.")
    promote.add_argument("id")
    promote.add_argument("--global-store", default=default_global_store())
    promote.add_argument("--target-project", default="global")
    promote.add_argument("--tag", action="append", default=[], help="Extra tag for promoted memory.")
    promote.add_argument("--with-raw", action="store_true", help="Also copy raw trace.")
    promote.add_argument("--archive-source", action="store_true", help="Archive the source project memory after promotion.")
    promote.add_argument("--json", action="store_true")

    curate = subparsers.add_parser("curate", help="Maintain memory records: find duplicates or merge records.")
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

    verify = subparsers.add_parser(
        "verify",
        help="Maintenance: verify file-protocol integrity without changing records.",
    )
    verify.add_argument("--json", action="store_true", help="Print a machine-readable report.")

    rebuild = subparsers.add_parser(
        "rebuild-index",
        help="Maintenance: rebuild the derived index from valid mail bodies.",
    )
    rebuild.add_argument("--json", action="store_true", help="Print a machine-readable report.")

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


def cmd_status(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    mail = store.update_status(args.id, args.status)
    if args.json:
        print_json(mail.to_index_entry().to_dict())
    else:
        print(f"{mail.id}\t{mail.status}")
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


def cmd_verify(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    report = store.verify()
    if args.json:
        print_json(report)
    else:
        print_verification_report(report, action="verified")
    return 0 if report["ok"] else 1


def cmd_rebuild_index(store: JsonMemoBoxStore, args: argparse.Namespace) -> int:
    report = store.rebuild_index()
    if args.json:
        print_json(report)
    else:
        action = "rebuilt" if report["rebuilt"] else "not rebuilt"
        print_verification_report(report, action=action)
    return 0 if report["ok"] and report["rebuilt"] else 1


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


def print_verification_report(report: dict[str, Any], action: str) -> None:
    print(
        f"{action}: {report['valid_mails']} valid mails, "
        f"{report['valid_index_entries']} valid index entries, "
        f"{report['trace_files']} traces"
    )
    for issue in report["issues"]:
        print(f"{issue['code']}\t{issue['path']}\t{issue['message']}")


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
