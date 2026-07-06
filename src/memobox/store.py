from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Iterable

from memobox.models import (
    IndexEntry,
    MemoryMail,
    MemoryStatus,
    utc_now_iso,
    validate_status,
)


class MemoBoxStoreError(RuntimeError):
    pass


class JsonMemoBoxStore:
    """File-backed MemoBox store with an index/body/raw-trace split."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self.mails_dir = self.root / "mails"
        self.traces_dir = self.root / "traces"

    def initialize(self) -> None:
        self.mails_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._atomic_write_text(self.index_path, "[]\n")

    def add_mail(
        self,
        mail: MemoryMail,
        raw_trace: Iterable[dict[str, Any] | str] | None = None,
    ) -> MemoryMail:
        self.initialize()
        if not mail.id:
            mail.id = self.generate_id(mail.subject)
        now = utc_now_iso()
        mail.created_at = mail.created_at or now
        mail.updated_at = now

        self._write_json(self.mail_path(mail.id), mail.to_dict())
        if raw_trace is not None:
            self.write_raw_trace(mail.id, raw_trace)
        self._upsert_index(mail.to_index_entry())
        return mail

    def list_index(self) -> list[IndexEntry]:
        self.initialize()
        data = self._read_json(self.index_path)
        if not isinstance(data, list):
            raise MemoBoxStoreError(f"Index must be a JSON array: {self.index_path}")
        return [IndexEntry.from_dict(item) for item in data]

    def get_index_entry(self, mail_id: str) -> IndexEntry:
        for entry in self.list_index():
            if entry.id == mail_id:
                return entry
        raise KeyError(f"Memory mail not found in index: {mail_id}")

    def open_mail(self, mail_id: str) -> MemoryMail:
        path = self.mail_path(mail_id)
        if not path.exists():
            raise KeyError(f"Memory mail body not found: {mail_id}")
        return MemoryMail.from_dict(self._read_json(path))

    def update_status(self, mail_id: str, status: MemoryStatus) -> MemoryMail:
        validate_status(status)
        mail = self.open_mail(mail_id)
        mail.status = status
        mail.updated_at = utc_now_iso()
        self._write_json(self.mail_path(mail.id), mail.to_dict())
        self._upsert_index(mail.to_index_entry())
        return mail

    def delete_mail(self, mail_id: str) -> None:
        current_entries = self.list_index()
        entries = [entry for entry in current_entries if entry.id != mail_id]
        if len(entries) == len(current_entries):
            raise KeyError(f"Memory mail not found: {mail_id}")
        self._write_index(entries)
        self.mail_path(mail_id).unlink(missing_ok=True)
        self.trace_path(mail_id).unlink(missing_ok=True)

    def write_raw_trace(
        self,
        mail_id: str,
        raw_trace: Iterable[dict[str, Any] | str],
    ) -> None:
        self.initialize()
        with self.trace_path(mail_id).open("w", encoding="utf-8") as handle:
            for event in raw_trace:
                if isinstance(event, str):
                    payload: dict[str, Any] = {"text": event}
                else:
                    payload = event
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                handle.write("\n")

    def open_raw_trace(self, mail_id: str) -> list[dict[str, Any]]:
        path = self.trace_path(mail_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def mail_path(self, mail_id: str) -> Path:
        return self.mails_dir / f"{mail_id}.json"

    def trace_path(self, mail_id: str) -> Path:
        return self.traces_dir / f"{mail_id}.jsonl"

    def generate_id(self, subject: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", subject.strip().lower()).strip("-")
        slug = slug[:48] or "memory"
        timestamp = utc_now_iso().replace("+00:00", "Z")
        timestamp = re.sub(r"[^0-9TZ]", "", timestamp)
        return f"{timestamp}-{slug}-{uuid.uuid4().hex[:8]}"

    def _upsert_index(self, entry: IndexEntry) -> None:
        entries = self.list_index()
        by_id = {item.id: item for item in entries}
        by_id[entry.id] = entry
        self._write_index(sorted(by_id.values(), key=lambda item: item.updated_at, reverse=True))

    def _write_index(self, entries: list[IndexEntry]) -> None:
        self.initialize()
        self._write_json(self.index_path, [entry.to_dict() for entry in entries])

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._atomic_write_text(path, payload)

    def _atomic_write_text(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, path)
