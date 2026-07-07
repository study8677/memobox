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


def test_cli_round_trip_with_storage_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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

    assert main(["--store", str(store_dir), "index", "--json"]) == 0
    index_payload = json.loads(capsys.readouterr().out)
    index_entry = index_payload["entries"][0]
    assert index_entry["id"] == mail_id
    assert "context" not in index_entry
    assert "decisions" not in index_entry
    assert "raw_trace" in index_entry
    assert index_entry["raw_trace"]["exists"] is True
    assert " read " in index_entry["mail_body"]["open_command"]
    assert " trace " in index_entry["raw_trace"]["open_command"]

    assert main(["--store", str(store_dir), "read", mail_id, "--json"]) == 0
    read_payload = json.loads(capsys.readouterr().out)
    assert read_payload["context"] == "Expandable details live here."
    assert "raw_trace" not in read_payload

    assert main(["--store", str(store_dir), "trace", mail_id, "--json"]) == 0
    trace_payload = json.loads(capsys.readouterr().out)
    assert trace_payload == [{"event": "done"}]

    assert main(["--store", str(store_dir), "status", mail_id, "archived"]) == 0
    capsys.readouterr()
    assert main(["--store", str(store_dir), "index", "--json"]) == 0
    archived_index_payload = json.loads(capsys.readouterr().out)
    assert archived_index_payload["entries"][0]["status"] == "archived"

    assert main(["--store", str(store_dir), "read", mail_id, "--json"]) == 0
    archived_read_payload = json.loads(capsys.readouterr().out)
    assert archived_read_payload["status"] == "archived"


def test_search_command_is_removed() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["search", "memobox"])
    assert exc_info.value.code == 2


def test_public_help_hides_legacy_commands() -> None:
    help_text = build_parser().format_help()
    assert "{init,write,index,read,status,trace,promote,curate}" in help_text
    assert "Write one Memory Mail record." in help_text
    assert "List memory index records without judging relevance." in help_text
    assert "{init,write,add" not in help_text
    assert "==SUPPRESS==" not in help_text
    assert "recall" not in help_text
    assert "remember" not in help_text


def test_legacy_commands_remain_available(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_store = JsonMemoBoxStore(tmp_path / "project")
    global_store = JsonMemoBoxStore(tmp_path / "global")
    global_store.add_mail(make_mail(2, subject="Global storage pattern", project="global"))
    raw_file = tmp_path / "raw.jsonl"
    raw_file.write_text('{"event":"legacy"}\n', encoding="utf-8")

    assert (
        main(
            [
                "--store",
                str(project_store.root),
                "add",
                "--subject",
                "Legacy add command",
                "--summary",
                "Compatibility write path.",
                "--raw-trace-file",
                str(raw_file),
            ]
        )
        == 0
    )
    mail_id = capsys.readouterr().out.strip()

    assert main(["--store", str(project_store.root), "inbox", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["entries"][0]["id"] == mail_id

    assert main(["--store", str(project_store.root), "map", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["entries"][0]["id"] == mail_id

    assert main(["--store", str(project_store.root), "show", mail_id, "--raw", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["raw_trace"] == [{"event": "legacy"}]

    assert main(["--store", str(project_store.root), "raw", mail_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"event": "legacy"}]

    assert (
        main(
            [
                "--store",
                str(project_store.root),
                "recall",
                "storage",
                "--global-store",
                str(global_store.root),
                "--json",
            ]
        )
        == 0
    )
    recall_payload = json.loads(capsys.readouterr().out)
    assert {store_payload["scope"] for store_payload in recall_payload["stores"]} == {"project", "global"}

    assert (
        main(
            [
                "--store",
                str(project_store.root),
                "remember",
                "--subject",
                "Legacy remember command",
                "--summary",
                "Compatibility memory write.",
                "--project",
                "memobox",
                "--json",
            ]
        )
        == 0
    )
    remember_payload = json.loads(capsys.readouterr().out)
    assert remember_payload["tags"] == ["task-memory"]


def test_index_lists_directory_without_judging_relevance(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = JsonMemoBoxStore(tmp_path / "project")
    store.add_mail(make_mail(1, subject="Project README polish", project="memobox"))
    store.add_mail(make_mail(2, subject="Archived deploy note", project="memobox", status="archived"))

    assert main(["--store", str(store.root), "index", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["scope"] == "project"
    assert payload["total_entries"] == 2
    assert {entry["id"] for entry in payload["entries"]} == {"task-1", "task-2"}
    assert all("score" not in entry for entry in payload["entries"])
    assert all("matched_terms" not in entry for entry in payload["entries"])
    assert all("context" not in entry for entry in payload["entries"])
    assert all("decisions" not in entry for entry in payload["entries"])
    assert payload["entries"][0]["mail_body"]["path"].endswith(".json")
    assert payload["entries"][0]["raw_trace"]["path"].endswith(".jsonl")


def test_index_paginates_without_filtering(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = JsonMemoBoxStore(tmp_path / "project")
    for index in range(3):
        store.add_mail(make_mail(index))

    assert main(["--store", str(store.root), "index", "--page", "2", "--per-page", "2", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["total_entries"] == 3
    assert payload["page"] == 2
    assert payload["per_page"] == 2
    assert len(payload["entries"]) == 1
    assert payload["has_previous"] is True
    assert payload["has_next"] is False


def test_index_can_explicitly_include_global_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_store = JsonMemoBoxStore(tmp_path / "project")
    global_store = JsonMemoBoxStore(tmp_path / "global")
    project_store.add_mail(make_mail(1, subject="Project README polish", project="memobox"))
    global_store.add_mail(make_mail(2, subject="Global README pattern", project="global"))
    global_store.add_mail(make_mail(3, subject="Unrelated archived note", project="global", status="archived"))

    assert (
        main(
            [
                "--store",
                str(project_store.root),
                "index",
                "--global-store",
                str(global_store.root),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert {store_payload["scope"] for store_payload in payload["stores"]} == {"project", "global"}
    entries_by_scope = {store_payload["scope"]: store_payload["entries"] for store_payload in payload["stores"]}
    assert {entry["id"] for entry in entries_by_scope["project"]} == {"task-1"}
    assert {entry["id"] for entry in entries_by_scope["global"]} == {"task-2", "task-3"}
    assert all("score" not in entry for entries in entries_by_scope.values() for entry in entries)
    assert all("matched_terms" not in entry for entries in entries_by_scope.values() for entry in entries)
    assert all("context" not in entry for entries in entries_by_scope.values() for entry in entries)


def test_index_tolerates_missing_global_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_store = JsonMemoBoxStore(tmp_path / "project")
    project_store.add_mail(make_mail(1, subject="Project only memory", project="memobox"))

    assert (
        main(
            [
                "--store",
                str(project_store.root),
                "index",
                "--global-store",
                str(tmp_path / "missing-global"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    entries_by_scope = {store_payload["scope"]: store_payload["entries"] for store_payload in payload["stores"]}
    assert [entry["id"] for entry in entries_by_scope["project"]] == ["task-1"]
    assert entries_by_scope["global"] == []


def test_legacy_remember_writes_standard_task_memory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "project"
    assert (
        main(
            [
                "--store",
                str(store_dir),
                "remember",
                "--subject",
                "Ship memory storage surface",
                "--summary",
                "Added compatibility command for standard task memory writes.",
                "--project",
                "memobox",
                "--team",
                "platform",
                "--tags",
                "storage,model",
                "--body",
                "MemoBox remains a memory store for model-directed use.",
                "--decision",
                "Use project and global stores together.",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == "memobox"
    assert payload["role"] == "memory-curator"
    assert payload["status"] == "inbox"
    assert payload["tags"] == ["task-memory", "storage", "model"]
    assert payload["decisions"] == ["Use project and global stores together."]


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


def test_curate_duplicates_merge_stale_and_pin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = JsonMemoBoxStore(tmp_path / "project")
    store.add_mail(make_mail(1, subject="Duplicate memory", tags=["one"], decisions=["A"]))
    store.add_mail(make_mail(2, subject="Duplicate memory", tags=["two"], decisions=["B"]))
    store.add_mail(make_mail(3, subject="Old stale API note", tags=["api"]))
    store.add_mail(make_mail(4, subject="Important launch memory", tags=["launch"]))

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

    assert main(["--store", str(store.root), "curate", "stale", "task-3", "--json"]) == 0
    stale_payload = json.loads(capsys.readouterr().out)
    assert stale_payload[0]["id"] == "task-3"
    assert stale_payload[0]["status"] == "stale"

    assert main(["--store", str(store.root), "curate", "pin", "task-4", "--json"]) == 0
    pin_payload = json.loads(capsys.readouterr().out)
    assert pin_payload[0]["id"] == "task-4"
    assert pin_payload[0]["status"] == "pinned"
