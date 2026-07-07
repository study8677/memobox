from __future__ import annotations

import json
from pathlib import Path

import pytest

from memobox.cli import build_parser, main
from memobox.models import MemoryMail
from memobox.store import JsonMemoBoxStore, MemoBoxStoreError


def make_mail(number: int, **overrides: object) -> MemoryMail:
    data = {
        "id": f"task-{number}",
        "subject": f"Task {number} memory routing",
        "summary": f"Summary for record {number} about MemoBox index storage surface.",
        "project": "model-memory",
        "workspace": "/workspace/model-memory",
        "team": "platform",
        "role": "model",
        "tags": ["memory", "memobox", f"task-{number}"],
        "participants": ["user", "model"],
        "importance": "normal",
        "status": "inbox",
        "confidence": 0.9,
        "context": f"Long body for task {number}; directory listings must not include this text.",
        "decisions": [f"Decision {number}"],
        "next_actions": [f"Next action {number}"],
    }
    data.update(overrides)
    return MemoryMail(**data)


def test_ten_tasks_create_one_mail_each_and_keep_index_light(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    for index in range(10):
        raw_trace = [{"event": "finished", "task": index}] if index == 3 else None
        store.add_mail(make_mail(index), raw_trace=raw_trace)

    entries = store.list_index()
    assert len(entries) == 10
    assert len(list((tmp_path / "memobox" / "mails").glob("*.json"))) == 10
    assert len(list((tmp_path / "memobox" / "traces").glob("*.jsonl"))) == 1

    index_payload = (tmp_path / "memobox" / "index.json").read_text(encoding="utf-8")
    assert "Long body" not in index_payload
    assert "Decision" not in index_payload
    assert "raw_trace" not in index_payload


def test_open_mail_and_raw_trace_are_explicit(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1), raw_trace=[{"turn": 1, "message": "raw"}])

    mail = store.open_mail("task-1")
    assert mail.context.startswith("Long body")
    assert store.open_raw_trace("task-1") == [{"message": "raw", "turn": 1}]
    assert store.open_raw_trace("missing") == []


def test_status_update_persists_to_index_and_body(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1))

    updated = store.update_status("task-1", "needs_review")
    assert updated.status == "needs_review"
    assert store.get_index_entry("task-1").status == "needs_review"
    assert store.open_mail("task-1").status == "needs_review"

    with pytest.raises(ValueError):
        store.update_status("task-1", "unknown")  # type: ignore[arg-type]


def test_corrupt_index_raises_useful_error(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.initialize()
    store.index_path.write_text('{"not": "a list"}', encoding="utf-8")

    with pytest.raises(MemoBoxStoreError, match="Index must be a JSON array"):
        store.list_index()


def test_cli_write_then_file_protocol_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "memobox"
    raw_file = tmp_path / "raw.jsonl"
    raw_file.write_text('{"event":"done"}\n', encoding="utf-8")

    assert main(["--store", str(store_dir), "init"]) == 0
    capsys.readouterr()

    assert (
        main(
            [
                "--store",
                str(store_dir),
                "write",
                "--subject",
                "Agent memobox system",
                "--summary",
                "Index-first model-readable memory storage.",
                "--project",
                "model-memory",
                "--team",
                "platform",
                "--role",
                "model",
                "--tags",
                "memory,memobox",
                "--body",
                "Expandable details live here.",
                "--decision",
                "Use task-level memory mails.",
                "--raw-trace-file",
                str(raw_file),
            ]
        )
        == 0
    )
    mail_id = capsys.readouterr().out.strip()

    index_payload = json.loads((store_dir / "index.json").read_text(encoding="utf-8"))
    index_entry = index_payload[0]
    assert index_entry["id"] == mail_id
    assert "context" not in index_entry
    assert "decisions" not in index_entry
    assert "raw_trace" not in index_entry

    mail_payload = json.loads((store_dir / "mails" / f"{mail_id}.json").read_text(encoding="utf-8"))
    assert mail_payload["context"] == "Expandable details live here."
    assert mail_payload["decisions"] == ["Use task-level memory mails."]
    assert "raw_trace" not in mail_payload

    trace_lines = (store_dir / "traces" / f"{mail_id}.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in trace_lines] == [{"event": "done"}]

    assert main(["--store", str(store_dir), "status", mail_id, "archived"]) == 0
    capsys.readouterr()
    archived_index_payload = json.loads((store_dir / "index.json").read_text(encoding="utf-8"))
    assert archived_index_payload[0]["status"] == "archived"
    archived_read_payload = json.loads((store_dir / "mails" / f"{mail_id}.json").read_text(encoding="utf-8"))
    assert archived_read_payload["status"] == "archived"


def test_search_command_is_removed() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["search", "memobox"])
    assert exc_info.value.code == 2


def test_public_help_hides_legacy_commands() -> None:
    help_text = build_parser().format_help()
    assert "{init,write,status,promote,curate}" in help_text
    assert "Write one Memory Mail record." in help_text
    assert "Read memory directly with Bash" in help_text
    assert "memobox index" not in help_text
    assert "memobox read" not in help_text
    assert "memobox trace" not in help_text
    assert " add " not in help_text
    assert "==SUPPRESS==" not in help_text
    assert "recall" not in help_text
    assert "remember" not in help_text


def test_reading_commands_and_legacy_aliases_are_removed() -> None:
    removed_commands = [
        ["index"],
        ["read", "task-1"],
        ["trace", "task-1"],
        ["add", "--subject", "Legacy", "--summary", "Legacy"],
        ["inbox"],
        ["map"],
        ["show", "task-1"],
        ["raw", "task-1"],
        ["recall", "storage"],
        ["remember", "--subject", "Legacy", "--summary", "Legacy", "--project", "memobox"],
    ]
    for command in removed_commands:
        with pytest.raises(SystemExit) as exc_info:
            main(command)
        assert exc_info.value.code == 2


def test_file_protocol_lists_directory_without_judging_relevance(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "project")
    store.add_mail(make_mail(1, subject="Project README polish", project="memobox"))
    store.add_mail(make_mail(2, subject="Archived deploy note", project="memobox", status="archived"))

    entries = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert {entry["id"] for entry in entries} == {"task-1", "task-2"}
    assert all("score" not in entry for entry in entries)
    assert all("matched_terms" not in entry for entry in entries)
    assert all("context" not in entry for entry in entries)
    assert all("decisions" not in entry for entry in entries)


def test_promote_copies_project_memory_to_global_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_store = JsonMemoBoxStore(tmp_path / "project")
    global_store_dir = tmp_path / "global"
    project_store.add_mail(make_mail(1), raw_trace=[{"event": "evidence"}])

    assert (
        main(
            [
                "--store",
                str(project_store.root),
                "promote",
                "task-1",
                "--global-store",
                str(global_store_dir),
                "--with-raw",
                "--archive-source",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    global_store = JsonMemoBoxStore(global_store_dir)
    promoted = global_store.open_mail(payload["promoted_id"])
    assert promoted.project == "global"
    assert "promoted" in promoted.tags
    assert promoted.source_refs[-1].ref.endswith(":task-1")
    assert global_store.open_raw_trace(promoted.id) == [{"event": "evidence"}]
    assert project_store.open_mail("task-1").status == "archived"


def test_curate_duplicates_and_merge(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = JsonMemoBoxStore(tmp_path / "project")
    store.add_mail(make_mail(1, subject="Duplicate memory", tags=["one"], decisions=["A"]))
    store.add_mail(make_mail(2, subject="Duplicate memory", tags=["two"], decisions=["B"]))

    assert main(["--store", str(store.root), "curate", "duplicates", "--json"]) == 0
    duplicates = json.loads(capsys.readouterr().out)
    assert duplicates[0]["key"] == "model-memory:duplicate memory"
    assert {entry["id"] for entry in duplicates[0]["entries"]} == {"task-1", "task-2"}

    assert (
        main(
            [
                "--store",
                str(store.root),
                "curate",
                "merge",
                "task-1",
                "task-2",
                "--subject",
                "Merged duplicate memory",
                "--summary",
                "Merged duplicate task memory.",
                "--json",
            ]
        )
        == 0
    )
    merge_payload = json.loads(capsys.readouterr().out)
    merged = store.open_mail(merge_payload["merged_id"])
    assert "merged" in merged.tags
    assert merged.decisions == ["A", "B"]
    assert store.open_mail("task-1").status == "archived"
    assert store.open_mail("task-2").status == "archived"
