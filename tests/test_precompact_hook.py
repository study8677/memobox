from __future__ import annotations

import json
from pathlib import Path

from memobox.hooks.precompact_snapshot import main as precompact_main
from memobox.store import JsonMemoBoxStore


def test_precompact_hook_skips_missing_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert precompact_main(["--store", ".memobox", "--trigger", "auto"], stdin_text='{"trigger":"auto"}') == 0

    assert not (tmp_path / ".memobox").exists()


def test_precompact_hook_writes_checkpoint_and_redacts_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = JsonMemoBoxStore(tmp_path / ".memobox")
    store.initialize()
    payload = {
        "trigger": "auto",
        "thread_id": "thread-123",
        "api_key": "sk-secret",
        "nested": {"token": "secret-token"},
    }

    assert precompact_main(["--store", ".memobox"], stdin_text=json.dumps(payload)) == 0

    entries = store.list_index()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.subject == "Codex pre-compact checkpoint (auto)"
    assert entry.status == "needs_review"
    assert {"codex", "precompact", "context", "checkpoint"}.issubset(set(entry.tags))

    mail = store.open_mail(entry.id)
    assert mail.role == "codex-hook"
    assert mail.project == tmp_path.name
    assert any("Full transcript capture is not guaranteed" in risk for risk in mail.risks)

    trace = store.open_raw_trace(entry.id)
    assert trace[0]["payload"]["api_key"] == "[REDACTED]"
    assert trace[0]["payload"]["nested"]["token"] == "[REDACTED]"


def test_plugin_bundles_precompact_hook_config() -> None:
    hook_config = json.loads(Path("hooks/hooks.json").read_text(encoding="utf-8"))

    group = hook_config["hooks"]["PreCompact"][0]
    assert group["matcher"] == "auto"
    assert "memobox-precompact-snapshot" in group["hooks"][0]["command"]
