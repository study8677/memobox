from __future__ import annotations

import json
from pathlib import Path

import pytest

from memobox.cli import main
from memobox.models import IndexEntry, MemoryMail
from memobox.search import MemoBoxSearcher
from memobox.store import JsonMemoBoxStore, MemoBoxStoreError


def make_mail(number: int, **overrides: object) -> MemoryMail:
    data = {
        "id": f"task-{number}",
        "subject": f"Task {number} memory routing",
        "summary": f"Summary for task {number} about agent MemoBox index retrieval.",
        "project": "agent-memory",
        "workspace": "/workspace/agent-memory",
        "team": "platform",
        "role": "main-agent",
        "tags": ["memory", "memobox", f"task-{number}"],
        "participants": ["user", "main-agent"],
        "importance": "normal",
        "status": "inbox",
        "confidence": 0.9,
        "context": f"Long body for task {number}; search must not need this text.",
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


def test_search_uses_index_only() -> None:
    class SpyStore:
        def __init__(self) -> None:
            self.list_index_calls = 0
            self.open_mail_calls = 0
            self.open_raw_trace_calls = 0

        def list_index(self) -> list[IndexEntry]:
            self.list_index_calls += 1
            return [
                IndexEntry(
                    id="task-1",
                    subject="Agent memobox routing",
                    summary="Index-first memory search for agents.",
                    project="agent-memory",
                    team="platform",
                    role="main-agent",
                    tags=["memobox", "memory"],
                    status="inbox",
                )
            ]

        def open_mail(self, mail_id: str) -> MemoryMail:
            self.open_mail_calls += 1
            raise AssertionError("search must not open memory mail bodies")

        def open_raw_trace(self, mail_id: str) -> list[dict[str, object]]:
            self.open_raw_trace_calls += 1
            raise AssertionError("search must not open raw traces")

    spy = SpyStore()
    results = MemoBoxSearcher(spy).search("memobox memory", project="agent-memory")
    assert [result.entry.id for result in results] == ["task-1"]
    assert spy.list_index_calls == 1
    assert spy.open_mail_calls == 0
    assert spy.open_raw_trace_calls == 0


def test_filters_and_status_defaults(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1, project="agent-memory", team="platform", role="main-agent"))
    store.add_mail(make_mail(2, project="billing", team="finance", role="worker"))
    store.add_mail(make_mail(3, project="agent-memory", status="archived"))

    searcher = MemoBoxSearcher(store)
    results = searcher.search("memobox", project="agent-memory", team="platform", role="main-agent")
    assert [result.entry.id for result in results] == ["task-1"]

    default_results = searcher.search("memobox", project="agent-memory")
    assert "task-3" not in {result.entry.id for result in default_results}

    all_status_results = searcher.search("memobox", project="agent-memory", statuses=None)
    assert "task-3" in {result.entry.id for result in all_status_results}


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


def test_cli_round_trip_and_raw_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
                "add",
                "--subject",
                "Agent memobox system",
                "--summary",
                "Index-first task memory for agents.",
                "--project",
                "agent-memory",
                "--team",
                "platform",
                "--role",
                "main-agent",
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

    assert main(["--store", str(store_dir), "search", "memobox", "--json"]) == 0
    search_payload = json.loads(capsys.readouterr().out)
    assert search_payload[0]["entry"]["id"] == mail_id
    assert "context" not in search_payload[0]["entry"]

    assert main(["--store", str(store_dir), "show", mail_id, "--json"]) == 0
    show_payload = json.loads(capsys.readouterr().out)
    assert show_payload["context"] == "Expandable details live here."
    assert "raw_trace" not in show_payload

    assert main(["--store", str(store_dir), "show", mail_id, "--raw", "--json"]) == 0
    show_raw_payload = json.loads(capsys.readouterr().out)
    assert show_raw_payload["raw_trace"] == [{"event": "done"}]

    assert main(["--store", str(store_dir), "status", mail_id, "archived"]) == 0
    capsys.readouterr()
    assert main(["--store", str(store_dir), "search", "memobox", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []

