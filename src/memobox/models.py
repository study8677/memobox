from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
import math
import re
from typing import Any, Literal

MemoryStatus = Literal["inbox", "pinned", "archived", "stale", "needs_review"]
Importance = Literal["low", "normal", "high", "critical"]
SCHEMA_VERSION = 2
VALID_STATUSES = {"inbox", "pinned", "archived", "stale", "needs_review"}
VALID_IMPORTANCE = {"low", "normal", "high", "critical"}
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Artifact:
    kind: str
    uri: str
    title: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        return cls(
            kind=str(data.get("kind", "")),
            uri=str(data.get("uri", "")),
            title=str(data.get("title", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceRef:
    kind: str
    ref: str
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRef":
        return cls(
            kind=str(data.get("kind", "")),
            ref=str(data.get("ref", "")),
            note=str(data.get("note", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IndexEntry:
    id: str
    subject: str
    summary: str
    schema_version: int = SCHEMA_VERSION
    project: str = ""
    workspace: str = ""
    team: str = ""
    role: str = ""
    tags: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    importance: Importance = "normal"
    status: MemoryStatus = "inbox"
    confidence: float = 1.0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    supersedes: list[str] = field(default_factory=list)
    last_verified_at: str | None = None
    valid_until: str | None = None

    def __post_init__(self) -> None:
        validate_status(self.status)
        validate_importance(self.importance)
        validate_confidence(self.confidence)
        validate_supersedes(self.supersedes)
        validate_iso_date_or_datetime(self.last_verified_at, "last_verified_at")
        validate_iso_date_or_datetime(self.valid_until, "valid_until")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexEntry":
        status = str(data.get("status", "inbox"))
        importance = str(data.get("importance", "normal"))
        confidence = data.get("confidence", 1.0)
        validate_status(status)
        validate_importance(importance)
        validate_confidence(confidence)
        return cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            id=str(data["id"]),
            subject=str(data.get("subject", "")),
            summary=str(data.get("summary", "")),
            project=str(data.get("project", "")),
            workspace=str(data.get("workspace", "")),
            team=str(data.get("team", "")),
            role=str(data.get("role", "")),
            tags=[str(item) for item in data.get("tags", [])],
            participants=[str(item) for item in data.get("participants", [])],
            importance=importance,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            confidence=float(confidence),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
            supersedes=parse_supersedes(data.get("supersedes", [])),
            last_verified_at=parse_optional_string(data.get("last_verified_at"), "last_verified_at"),
            valid_until=parse_optional_string(data.get("valid_until"), "valid_until"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        omit_empty_optional_fields(data)
        return data


@dataclass(slots=True)
class MemoryMail:
    id: str
    subject: str
    summary: str
    schema_version: int = SCHEMA_VERSION
    project: str = ""
    workspace: str = ""
    team: str = ""
    role: str = ""
    tags: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    importance: Importance = "normal"
    status: MemoryStatus = "inbox"
    confidence: float = 1.0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    context: str = ""
    decisions: list[str] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    source_refs: list[SourceRef] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    last_verified_at: str | None = None
    valid_until: str | None = None

    def __post_init__(self) -> None:
        validate_status(self.status)
        validate_importance(self.importance)
        validate_confidence(self.confidence)
        validate_supersedes(self.supersedes)
        validate_iso_date_or_datetime(self.last_verified_at, "last_verified_at")
        validate_iso_date_or_datetime(self.valid_until, "valid_until")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryMail":
        status = str(data.get("status", "inbox"))
        importance = str(data.get("importance", "normal"))
        confidence = data.get("confidence", 1.0)
        validate_status(status)
        validate_importance(importance)
        validate_confidence(confidence)
        return cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            id=str(data["id"]),
            subject=str(data.get("subject", "")),
            summary=str(data.get("summary", "")),
            project=str(data.get("project", "")),
            workspace=str(data.get("workspace", "")),
            team=str(data.get("team", "")),
            role=str(data.get("role", "")),
            tags=[str(item) for item in data.get("tags", [])],
            participants=[str(item) for item in data.get("participants", [])],
            importance=importance,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            confidence=float(confidence),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
            context=str(data.get("context", "")),
            decisions=[str(item) for item in data.get("decisions", [])],
            artifacts=[Artifact.from_dict(item) for item in data.get("artifacts", [])],
            next_actions=[str(item) for item in data.get("next_actions", [])],
            risks=[str(item) for item in data.get("risks", [])],
            source_refs=[SourceRef.from_dict(item) for item in data.get("source_refs", [])],
            supersedes=parse_supersedes(data.get("supersedes", [])),
            last_verified_at=parse_optional_string(data.get("last_verified_at"), "last_verified_at"),
            valid_until=parse_optional_string(data.get("valid_until"), "valid_until"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        data["source_refs"] = [source_ref.to_dict() for source_ref in self.source_refs]
        omit_empty_optional_fields(data)
        return data

    def to_index_entry(self) -> IndexEntry:
        return IndexEntry(
            id=self.id,
            schema_version=self.schema_version,
            subject=self.subject,
            summary=self.summary,
            project=self.project,
            workspace=self.workspace,
            team=self.team,
            role=self.role,
            tags=list(self.tags),
            participants=list(self.participants),
            importance=self.importance,
            status=self.status,
            confidence=self.confidence,
            created_at=self.created_at,
            updated_at=self.updated_at,
            supersedes=list(self.supersedes),
            last_verified_at=self.last_verified_at,
            valid_until=self.valid_until,
        )


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        allowed = ", ".join(sorted(VALID_STATUSES))
        raise ValueError(f"Invalid memory status {status!r}. Expected one of: {allowed}")


def validate_importance(importance: str) -> None:
    if importance not in VALID_IMPORTANCE:
        allowed = ", ".join(sorted(VALID_IMPORTANCE))
        raise ValueError(f"Invalid importance {importance!r}. Expected one of: {allowed}")


def validate_confidence(confidence: float) -> None:
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("Confidence must be a finite number between 0.0 and 1.0")
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be a finite number between 0.0 and 1.0")


def parse_supersedes(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("supersedes must be a JSON array of memory mail ids")
    supersedes = list(value)
    validate_supersedes(supersedes)
    return supersedes


def validate_supersedes(supersedes: list[str]) -> None:
    if not isinstance(supersedes, list) or any(
        not isinstance(mail_id, str) or not mail_id for mail_id in supersedes
    ):
        raise ValueError("supersedes must be a list of non-empty memory mail ids")


def parse_optional_string(value: Any, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO 8601 date or timezone-aware datetime")
    return value


def validate_iso_date_or_datetime(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be an ISO 8601 date or timezone-aware datetime")
    try:
        if ISO_DATE_PATTERN.fullmatch(value):
            date.fromisoformat(value)
            return
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO 8601 date or timezone-aware datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"{field_name} datetime must include a timezone offset or Z suffix"
        )


def omit_empty_optional_fields(data: dict[str, Any]) -> None:
    for field_name in ("supersedes", "last_verified_at", "valid_until"):
        if not data.get(field_name):
            data.pop(field_name, None)
