from __future__ import annotations

import errno
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from memobox.models import (
    IndexEntry,
    MemoryMail,
    MemoryStatus,
    utc_now_iso,
    validate_confidence,
    validate_importance,
    validate_status,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]


MAIL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
WINDOWS_LOCK_TIMEOUT_SECONDS = 30.0
WINDOWS_LOCK_RETRY_ERRNOS = {errno.EACCES, errno.EAGAIN, errno.EDEADLK}


class MemoBoxStoreError(RuntimeError):
    pass


class JsonMemoBoxStore:
    """File-backed MemoBox store with mails as its source of truth."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self.mails_dir = self.root / "mails"
        self.traces_dir = self.root / "traces"
        self.lock_path = self.root / ".lock"

    def initialize(self) -> None:
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()

    def add_mail(
        self,
        mail: MemoryMail,
        raw_trace: Iterable[dict[str, Any] | str] | None = None,
    ) -> MemoryMail:
        validate_status(mail.status)
        validate_importance(mail.importance)
        validate_confidence(mail.confidence)
        if not mail.id:
            mail.id = self.generate_id(mail.subject)
        validate_mail_id(mail.id)

        now = utc_now_iso()
        mail.created_at = mail.created_at or now
        mail.updated_at = now
        trace_payload = self._serialize_raw_trace(raw_trace) if raw_trace is not None else None

        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            self._assert_mails_valid_unlocked()
            self._write_json(self.mail_path(mail.id), mail.to_dict())
            if trace_payload is not None:
                self._atomic_write_text(self.trace_path(mail.id), trace_payload)
            self._rebuild_index_file_unlocked()
        return mail

    def list_index(self) -> list[IndexEntry]:
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            return self._read_index_unlocked()

    def get_index_entry(self, mail_id: str) -> IndexEntry:
        validate_mail_id(mail_id)
        for entry in self.list_index():
            if entry.id == mail_id:
                return entry
        raise KeyError(f"Memory mail not found in index: {mail_id}")

    def open_mail(self, mail_id: str) -> MemoryMail:
        validate_mail_id(mail_id)
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            return self._open_mail_unlocked(mail_id)

    def update_status(self, mail_id: str, status: MemoryStatus) -> MemoryMail:
        validate_mail_id(mail_id)
        validate_status(status)
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            self._assert_mails_valid_unlocked()
            mail = self._open_mail_unlocked(mail_id)
            mail.status = status
            mail.updated_at = utc_now_iso()
            self._write_json(self.mail_path(mail_id), mail.to_dict())
            self._rebuild_index_file_unlocked()
            return mail

    def delete_mail(self, mail_id: str) -> None:
        validate_mail_id(mail_id)
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            path = self.mail_path(mail_id)
            if not path.exists():
                raise KeyError(f"Memory mail body not found: {mail_id}")
            if path.is_symlink():
                raise MemoBoxStoreError(f"Memory mail body must not be a symlink: {path}")
            path.unlink()
            self.trace_path(mail_id).unlink(missing_ok=True)
            self._rebuild_index_file_unlocked()

    def write_raw_trace(
        self,
        mail_id: str,
        raw_trace: Iterable[dict[str, Any] | str],
    ) -> None:
        validate_mail_id(mail_id)
        payload = self._serialize_raw_trace(raw_trace)
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            self._open_mail_unlocked(mail_id)
            self._atomic_write_text(self.trace_path(mail_id), payload)

    def open_raw_trace(self, mail_id: str) -> list[dict[str, Any]]:
        validate_mail_id(mail_id)
        self._prepare_directories()
        with self._exclusive_lock():
            self._initialize_unlocked()
            path = self.trace_path(mail_id)
            if not path.exists():
                return []
            if path.is_symlink():
                raise MemoBoxStoreError(f"Raw trace must not be a symlink: {path}")
            events: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise MemoBoxStoreError(
                            f"Raw trace event must be a JSON object: {path}:{line_number}"
                        )
                    events.append(event)
            return events

    def verify(self) -> dict[str, Any]:
        """Inspect store consistency without repairing or deleting user data."""
        self._prepare_directories()
        with self._exclusive_lock():
            return self._verify_unlocked()

    def rebuild_index(self) -> dict[str, Any]:
        """Rebuild the derived index if every mail body is valid."""
        self._prepare_directories()
        with self._exclusive_lock():
            mails, mail_issues, _ = self._scan_mails_unlocked()
            if mail_issues:
                report = self._verify_unlocked()
                report.update({"rebuilt": False, "indexed_mails": 0})
                return report
            self._write_index_unlocked(
                sorted(
                    (mail.to_index_entry() for mail in mails.values()),
                    key=lambda item: (item.updated_at, item.id),
                    reverse=True,
                )
            )
            report = self._verify_unlocked()
            report.update({"rebuilt": True, "indexed_mails": len(mails)})
            return report

    def mail_path(self, mail_id: str) -> Path:
        validate_mail_id(mail_id)
        return self.mails_dir / f"{mail_id}.json"

    def trace_path(self, mail_id: str) -> Path:
        validate_mail_id(mail_id)
        return self.traces_dir / f"{mail_id}.jsonl"

    def generate_id(self, subject: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", subject.strip().lower()).strip("-")
        slug = slug[:48] or "memory"
        timestamp = utc_now_iso().replace("+00:00", "Z")
        timestamp = re.sub(r"[^0-9TZ]", "", timestamp)
        return f"{timestamp}-{slug}-{uuid.uuid4().hex[:8]}"

    def _prepare_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in (self.mails_dir, self.traces_dir):
            if directory.is_symlink():
                raise MemoBoxStoreError(f"Store directory must not be a symlink: {directory}")
            directory.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.lock_path.is_symlink():
            raise MemoBoxStoreError(f"Lock file must not be a symlink: {self.lock_path}")
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            self._lock_file(lock_file)
            try:
                yield
            finally:
                self._unlock_file(lock_file)

    def _lock_file(self, lock_file: Any) -> None:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            return
        if msvcrt is None:  # pragma: no cover - unsupported platform
            raise MemoBoxStoreError("No supported cross-process file locking API is available")
        lock_file.seek(0)
        if not lock_file.read(1):
            lock_file.write("\0")
            lock_file.flush()
            os.fsync(lock_file.fileno())
        deadline = time.monotonic() + WINDOWS_LOCK_TIMEOUT_SECONDS
        while True:  # pragma: no cover - Windows
            try:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in WINDOWS_LOCK_RETRY_ERRNOS:
                    raise MemoBoxStoreError(f"Cannot acquire store lock: {exc}") from exc
                if time.monotonic() >= deadline:
                    raise MemoBoxStoreError(
                        f"Timed out acquiring store lock after {WINDOWS_LOCK_TIMEOUT_SECONDS:.0f}s"
                    ) from exc
                time.sleep(0.05)

    def _unlock_file(self, lock_file: Any) -> None:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            return
        if msvcrt is not None:  # pragma: no cover - Windows
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

    def _initialize_unlocked(self) -> None:
        if self.index_path.is_symlink():
            raise MemoBoxStoreError(f"Index must not be a symlink: {self.index_path}")
        if not self.index_path.exists():
            self._rebuild_index_file_unlocked()

    def _open_mail_unlocked(self, mail_id: str) -> MemoryMail:
        path = self.mail_path(mail_id)
        if not path.exists():
            raise KeyError(f"Memory mail body not found: {mail_id}")
        if path.is_symlink():
            raise MemoBoxStoreError(f"Memory mail body must not be a symlink: {path}")
        mail = self._read_mail_file(path)
        if mail.id != mail_id:
            raise MemoBoxStoreError(
                f"Memory mail id does not match filename: {path} contains {mail.id!r}"
            )
        return mail

    def _assert_mails_valid_unlocked(self) -> None:
        _, issues, _ = self._scan_mails_unlocked()
        if issues:
            first = issues[0]
            raise MemoBoxStoreError(
                f"Cannot update store while mail bodies are invalid; "
                f"run 'memobox verify': {first['message']}"
            )

    def _rebuild_index_file_unlocked(self) -> int:
        mails, issues, _ = self._scan_mails_unlocked()
        if issues:
            first = issues[0]
            raise MemoBoxStoreError(
                f"Cannot rebuild index while mail bodies are invalid: {first['message']}"
            )
        entries = sorted(
            (mail.to_index_entry() for mail in mails.values()),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        self._write_index_unlocked(entries)
        return len(entries)

    def _read_index_unlocked(self) -> list[IndexEntry]:
        try:
            data = self._read_json(self.index_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MemoBoxStoreError(f"Invalid JSON index {self.index_path}: {exc}") from exc
        if not isinstance(data, list):
            raise MemoBoxStoreError(f"Index must be a JSON array: {self.index_path}")
        entries: list[IndexEntry] = []
        for position, item in enumerate(data):
            if not isinstance(item, dict):
                raise MemoBoxStoreError(
                    f"Index entry {position} must be a JSON object: {self.index_path}"
                )
            try:
                entry = IndexEntry.from_dict(item)
                validate_mail_id(entry.id)
            except (KeyError, TypeError, ValueError) as exc:
                raise MemoBoxStoreError(
                    f"Invalid index entry {position} in {self.index_path}: {exc}"
                ) from exc
            entries.append(entry)
        return entries

    def _scan_mails_unlocked(
        self,
    ) -> tuple[dict[str, MemoryMail], list[dict[str, Any]], int]:
        mails: dict[str, MemoryMail] = {}
        issues: list[dict[str, Any]] = []
        paths = sorted(self.mails_dir.glob("*.json"))
        for path in paths:
            mail_id = path.stem
            if path.is_symlink():
                issues.append(
                    self._issue("mail_symlink", path, "Memory mail body must not be a symlink")
                )
                continue
            try:
                validate_mail_id(mail_id)
            except ValueError as exc:
                issues.append(self._issue("invalid_mail_filename", path, str(exc)))
                continue
            try:
                mail = self._read_mail_file(path)
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
                AttributeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                issues.append(self._issue("invalid_mail", path, f"Invalid memory mail: {exc}"))
                continue
            if mail.id != mail_id:
                issues.append(
                    self._issue(
                        "mail_id_mismatch",
                        path,
                        f"Body id {mail.id!r} does not match filename id {mail_id!r}",
                        mail_id=mail_id,
                    )
                )
                continue
            if mail.id in mails:
                issues.append(
                    self._issue(
                        "duplicate_mail_id",
                        path,
                        f"Duplicate memory mail id {mail.id!r}",
                        mail_id=mail.id,
                    )
                )
                continue
            mails[mail.id] = mail
        return mails, issues, len(paths)

    def _scan_index_unlocked(
        self,
    ) -> tuple[dict[str, IndexEntry], list[dict[str, Any]], int]:
        entries: dict[str, IndexEntry] = {}
        issues: list[dict[str, Any]] = []
        if self.index_path.is_symlink():
            return {}, [self._issue("index_symlink", self.index_path, "Index must not be a symlink")], 0
        if not self.index_path.exists():
            return {}, [self._issue("missing_index", self.index_path, "Index file is missing")], 0
        try:
            data = self._read_json(self.index_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {}, [self._issue("invalid_index", self.index_path, f"Invalid JSON index: {exc}")], 0
        if not isinstance(data, list):
            return {}, [self._issue("invalid_index", self.index_path, "Index must be a JSON array")], 0
        for position, item in enumerate(data):
            if not isinstance(item, dict):
                issues.append(
                    self._issue(
                        "invalid_index_entry",
                        self.index_path,
                        f"Index entry {position} must be a JSON object",
                        position=position,
                    )
                )
                continue
            try:
                entry = IndexEntry.from_dict(item)
                validate_mail_id(entry.id)
            except (KeyError, TypeError, ValueError) as exc:
                issues.append(
                    self._issue(
                        "invalid_index_entry",
                        self.index_path,
                        f"Invalid index entry {position}: {exc}",
                        position=position,
                    )
                )
                continue
            if entry.id in entries:
                issues.append(
                    self._issue(
                        "duplicate_index_id",
                        self.index_path,
                        f"Duplicate index id {entry.id!r}",
                        mail_id=entry.id,
                        position=position,
                    )
                )
                continue
            entries[entry.id] = entry
        return entries, issues, len(data)

    def _scan_traces_unlocked(
        self, valid_mail_ids: set[str]
    ) -> tuple[list[dict[str, Any]], int]:
        issues: list[dict[str, Any]] = []
        paths = sorted(self.traces_dir.glob("*.jsonl"))
        for path in paths:
            mail_id = path.stem
            if path.is_symlink():
                issues.append(self._issue("trace_symlink", path, "Raw trace must not be a symlink"))
                continue
            try:
                validate_mail_id(mail_id)
            except ValueError as exc:
                issues.append(self._issue("invalid_trace_filename", path, str(exc)))
                continue
            if mail_id not in valid_mail_ids:
                issues.append(
                    self._issue(
                        "orphan_trace",
                        path,
                        f"Raw trace has no valid memory mail body for {mail_id!r}",
                        mail_id=mail_id,
                    )
                )
            line_number = 0
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("trace event must be a JSON object")
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                issues.append(
                    self._issue(
                        "invalid_trace",
                        path,
                        f"Invalid raw trace at line {line_number}: {exc}",
                        mail_id=mail_id,
                        line=line_number,
                    )
                )
        return issues, len(paths)

    def _verify_unlocked(self) -> dict[str, Any]:
        mails, mail_issues, mail_file_count = self._scan_mails_unlocked()
        index, index_issues, index_entry_count = self._scan_index_unlocked()
        trace_issues, trace_file_count = self._scan_traces_unlocked(set(mails))
        issues = [*mail_issues, *index_issues]

        for mail_id, mail in sorted(mails.items()):
            entry = index.get(mail_id)
            if entry is None:
                issues.append(
                    self._issue(
                        "missing_index_entry",
                        self.index_path,
                        f"Valid memory mail {mail_id!r} is missing from index",
                        mail_id=mail_id,
                    )
                )
            elif entry.to_dict() != mail.to_index_entry().to_dict():
                issues.append(
                    self._issue(
                        "stale_index_entry",
                        self.index_path,
                        f"Index entry for {mail_id!r} does not match its memory mail body",
                        mail_id=mail_id,
                    )
                )
        for mail_id in sorted(set(index) - set(mails)):
            issues.append(
                self._issue(
                    "dangling_index_entry",
                    self.index_path,
                    f"Index entry {mail_id!r} has no valid memory mail body",
                    mail_id=mail_id,
                )
            )
        issues.extend(trace_issues)

        return {
            "ok": not issues,
            "root": str(self.root),
            "mail_files": mail_file_count,
            "valid_mails": len(mails),
            "index_entries": index_entry_count,
            "valid_index_entries": len(index),
            "trace_files": trace_file_count,
            "issues": issues,
        }

    def _read_mail_file(self, path: Path) -> MemoryMail:
        data = self._read_json(path)
        if not isinstance(data, dict):
            raise ValueError("Memory mail must be a JSON object")
        return MemoryMail.from_dict(data)

    def _write_index_unlocked(self, entries: list[IndexEntry]) -> None:
        self._write_json(self.index_path, [entry.to_dict() for entry in entries])

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
        self._atomic_write_text(path, payload)

    def _serialize_raw_trace(
        self, raw_trace: Iterable[dict[str, Any] | str]
    ) -> str:
        lines: list[str] = []
        for event in raw_trace:
            if isinstance(event, str):
                payload: dict[str, Any] = {"text": event}
            elif isinstance(event, dict):
                payload = event
            else:
                raise TypeError("Raw trace events must be dictionaries or strings")
            lines.append(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    allow_nan=False,
                )
            )
        return "".join(f"{line}\n" for line in lines)

    def _atomic_write_text(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temp_path.open("x", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            self._fsync_directory(path.parent)
        finally:
            temp_path.unlink(missing_ok=True)

    def _fsync_directory(self, path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            directory_fd = os.open(path, flags)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _issue(
        self,
        code: str,
        path: Path,
        message: str,
        **details: Any,
    ) -> dict[str, Any]:
        try:
            display_path = str(path.relative_to(self.root))
        except ValueError:
            display_path = str(path)
        return {"code": code, "path": display_path, "message": message, **details}


def validate_mail_id(mail_id: str) -> None:
    if not isinstance(mail_id, str) or not MAIL_ID_PATTERN.fullmatch(mail_id):
        raise ValueError(
            "Memory mail id must be 1-128 ASCII characters, start with an "
            "alphanumeric character, and contain only letters, numbers, '.', '_' or '-'"
        )
