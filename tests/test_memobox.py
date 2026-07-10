from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

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
    assert "{init,write,status,promote,curate,verify,rebuild-index}" in help_text
    assert "Write one Memory Mail record." in help_text
    assert "Maintenance: verify file-protocol integrity" in help_text
    assert "Maintenance: rebuild the derived index" in help_text
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
    project_store.add_mail(make_mail(0))
    project_store.add_mail(
        make_mail(
            1,
            supersedes=["task-0"],
            last_verified_at="2026-07-10T17:30:00+08:00",
            valid_until="2026-10-10",
        ),
        raw_trace=[{"event": "evidence"}],
    )

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
    assert promoted.source_refs[-1].ref == f"{project_store.root.resolve()}:task-1"
    assert payload["project_store"] == str(project_store.root.resolve())
    assert payload["global_store"] == str(global_store_dir.resolve())
    assert promoted.supersedes == []
    assert promoted.last_verified_at == "2026-07-10T17:30:00+08:00"
    assert promoted.valid_until == "2026-10-10"
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


def test_concurrent_subprocess_writes_keep_every_mail_in_index(tmp_path: Path) -> None:
    store_dir = tmp_path / "concurrent"
    source_root = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(source_root)
    )
    script = """
import sys
from memobox.models import MemoryMail
from memobox.store import JsonMemoBoxStore

number = int(sys.argv[2])
JsonMemoBoxStore(sys.argv[1]).add_mail(
    MemoryMail(
        id=f"concurrent-{number}",
        subject=f"Concurrent {number}",
        summary=f"Concurrent summary {number}",
    )
)
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(store_dir), str(number)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for number in range(32)
    ]
    failures: list[str] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        if process.returncode != 0:
            failures.append(f"stdout={stdout!r} stderr={stderr!r}")

    assert failures == []
    store = JsonMemoBoxStore(store_dir)
    assert {entry.id for entry in store.list_index()} == {
        f"concurrent-{number}" for number in range(32)
    }
    assert len(list(store.mails_dir.glob("*.json"))) == 32
    assert list(store.root.rglob("*.tmp")) == []
    assert store.verify()["ok"] is True


def test_verify_and_rebuild_index_recover_orphan_mail_and_corrupt_index(
    tmp_path: Path,
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1))
    orphan = make_mail(2)
    store.mail_path(orphan.id).write_text(
        json.dumps(orphan.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    store.index_path.write_text("{not-json", encoding="utf-8")

    verification = store.verify()
    assert verification["ok"] is False
    assert {issue["code"] for issue in verification["issues"]} >= {
        "invalid_index",
        "missing_index_entry",
    }

    rebuilt = store.rebuild_index()
    assert rebuilt["rebuilt"] is True
    assert rebuilt["ok"] is True
    assert {entry.id for entry in store.list_index()} == {"task-1", "task-2"}


def test_rebuild_index_refuses_partial_result_when_any_mail_is_corrupt(
    tmp_path: Path,
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1))
    original_index = store.index_path.read_bytes()
    (store.mails_dir / "broken.json").write_text("{broken", encoding="utf-8")

    report = store.rebuild_index()

    assert report["rebuilt"] is False
    assert report["ok"] is False
    assert any(issue["code"] == "invalid_mail" for issue in report["issues"])
    assert store.index_path.read_bytes() == original_index


def test_verify_detects_stale_dangling_index_and_invalid_trace(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1))
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    index[0]["summary"] = "stale"
    index.append(make_mail(2).to_index_entry().to_dict())
    store.index_path.write_text(json.dumps(index), encoding="utf-8")
    store.trace_path("task-1").write_text("not-json\n", encoding="utf-8")

    report = store.verify()
    codes = {issue["code"] for issue in report["issues"]}
    assert {"stale_index_entry", "dangling_index_entry", "invalid_trace"} <= codes


def test_cli_verify_and_rebuild_index_have_json_reports_and_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1))

    assert main(["--store", str(store.root), "verify", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    store.index_path.write_text("[]\n", encoding="utf-8")
    assert main(["--store", str(store.root), "verify", "--json"]) == 1
    broken_report = json.loads(capsys.readouterr().out)
    assert broken_report["issues"][0]["code"] == "missing_index_entry"

    assert main(["--store", str(store.root), "rebuild-index", "--json"]) == 0
    rebuilt_report = json.loads(capsys.readouterr().out)
    assert rebuilt_report["rebuilt"] is True
    assert rebuilt_report["ok"] is True


def test_mail_ids_cannot_escape_store_and_body_id_must_match_filename(
    tmp_path: Path,
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.initialize()
    unsafe_ids = [".", "..", "../escape", "a/b", r"a\b", "/tmp/escape", "a" * 129]
    with pytest.raises(ValueError, match="Memory mail id"):
        store.mail_path("")
    for unsafe_id in unsafe_ids:
        with pytest.raises(ValueError, match="Memory mail id"):
            store.mail_path(unsafe_id)
        with pytest.raises(ValueError, match="Memory mail id"):
            store.add_mail(make_mail(1, id=unsafe_id))

    malicious = make_mail(1, id="../../escape").to_dict()
    store.mail_path("safe").write_text(json.dumps(malicious), encoding="utf-8")
    with pytest.raises(MemoBoxStoreError, match="does not match filename"):
        store.open_mail("safe")
    with pytest.raises(MemoBoxStoreError, match="mail bodies are invalid"):
        store.update_status("safe", "archived")
    assert not (tmp_path / "escape.json").exists()


def test_confidence_must_be_finite_and_between_zero_and_one() -> None:
    assert make_mail(1, confidence=0.0).confidence == 0.0
    assert make_mail(1, confidence=1.0).confidence == 1.0
    for invalid in [-0.1, 1.1, float("nan"), float("inf"), float("-inf"), True]:
        with pytest.raises(ValueError, match="Confidence"):
            make_mail(1, confidence=invalid)
    with pytest.raises(ValueError, match="Confidence"):
        MemoryMail.from_dict(make_mail(1).to_dict() | {"confidence": True})


def test_invalid_trace_event_does_not_truncate_existing_trace(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1), raw_trace=[{"event": "kept"}])
    original = store.trace_path("task-1").read_bytes()

    with pytest.raises(TypeError, match="dictionaries or strings"):
        store.write_raw_trace("task-1", [object()])  # type: ignore[list-item]

    assert store.trace_path("task-1").read_bytes() == original
    assert list(store.traces_dir.glob("*.tmp")) == []


def test_trace_requires_an_existing_mail_body(tmp_path: Path) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")

    with pytest.raises(KeyError, match="Memory mail body not found"):
        store.write_raw_trace("missing", [{"event": "orphan"}])

    assert not store.trace_path("missing").exists()


def test_cli_write_supersedes_existing_memories_and_exposes_freshness(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1, status="pinned"))
    store.add_mail(make_mail(2))

    assert (
        main(
            [
                "--store",
                str(store.root),
                "write",
                "--subject",
                "Current memory",
                "--summary",
                "Replaces two older records.",
                "--supersedes",
                "task-1",
                "--supersedes",
                "task-1",
                "--supersedes",
                "task-2",
                "--last-verified-at",
                "2026-07-10T17:30:00+08:00",
                "--valid-until",
                "2026-10-10",
                "--json",
            ]
        )
        == 0
    )
    replacement_payload = json.loads(capsys.readouterr().out)
    replacement = store.open_mail(replacement_payload["id"])

    assert replacement.schema_version == 2
    assert replacement.supersedes == ["task-1", "task-2"]
    assert replacement.last_verified_at == "2026-07-10T17:30:00+08:00"
    assert replacement.valid_until == "2026-10-10"
    assert {(ref.kind, ref.ref, ref.note) for ref in replacement.source_refs} >= {
        ("memobox", "task-1", "superseded memory"),
        ("memobox", "task-2", "superseded memory"),
    }
    assert store.open_mail("task-1").status == "stale"
    assert store.open_mail("task-2").status == "stale"

    replacement_index = store.get_index_entry(replacement.id)
    assert replacement_index.supersedes == ["task-1", "task-2"]
    assert replacement_index.last_verified_at == replacement.last_verified_at
    assert replacement_index.valid_until == replacement.valid_until
    assert "context" not in replacement_index.to_dict()


def test_supersedes_rejects_missing_and_self_references_without_partial_write(
    tmp_path: Path,
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.add_mail(make_mail(1))

    with pytest.raises(KeyError, match="Memory mail body not found: missing"):
        store.add_mail(make_mail(2, supersedes=["missing"]))
    assert {entry.id for entry in store.list_index()} == {"task-1"}
    assert store.open_mail("task-1").status == "inbox"

    with pytest.raises(ValueError, match="cannot supersede itself"):
        store.add_mail(make_mail(2, supersedes=["task-2"]))
    assert {entry.id for entry in store.list_index()} == {"task-1"}


def test_freshness_dates_require_iso_8601_and_timezone_for_datetimes() -> None:
    assert make_mail(1, last_verified_at="2026-07-10").last_verified_at == "2026-07-10"
    assert make_mail(1, valid_until="2026-07-10T09:00:00Z").valid_until == (
        "2026-07-10T09:00:00Z"
    )

    for field_name, invalid in [
        ("last_verified_at", "2026-13-10"),
        ("last_verified_at", "2026-07-10T09:00:00"),
        ("valid_until", "next quarter"),
        ("valid_until", 20260710),
    ]:
        with pytest.raises(ValueError, match=field_name):
            make_mail(2, **{field_name: invalid})

    with pytest.raises(ValueError, match="supersedes"):
        MemoryMail.from_dict(make_mail(2).to_dict() | {"supersedes": [1]})


def test_schema_v1_mail_without_supersession_or_freshness_remains_readable(
    tmp_path: Path,
) -> None:
    store = JsonMemoBoxStore(tmp_path / "memobox")
    store.initialize()
    v1_payload = make_mail(1).to_dict()
    v1_payload["schema_version"] = 1
    for field_name in ("supersedes", "last_verified_at", "valid_until"):
        v1_payload.pop(field_name, None)
    store.mail_path("task-1").write_text(
        json.dumps(v1_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    rebuilt = store.rebuild_index()
    restored = store.open_mail("task-1")

    assert rebuilt["ok"] is True
    assert restored.schema_version == 1
    assert restored.supersedes == []
    assert restored.last_verified_at is None
    assert restored.valid_until is None
    assert "supersedes" not in restored.to_dict()
    assert store.get_index_entry("task-1").schema_version == 1


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation may require privileges")
def test_store_data_directories_cannot_be_symlinks(tmp_path: Path) -> None:
    store_root = tmp_path / "memobox"
    outside = tmp_path / "outside"
    store_root.mkdir()
    outside.mkdir()
    (store_root / "mails").symlink_to(outside, target_is_directory=True)
    store = JsonMemoBoxStore(store_root)

    with pytest.raises(MemoBoxStoreError, match="Store directory must not be a symlink"):
        store.initialize()
