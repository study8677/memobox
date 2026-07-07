from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

MemoryStatus = Literal["inbox", "pinned", "archived", "stale", "needs_review"]
Importance = Literal["low", "normal", "high", "critical"]
SCHEMA_VERSION = 1
VALID_STATUSES = {"inbox", "pinned", "archived", "stale", "needs_review"}
VALID_IMPORTANCE = {"low", "normal", "high", "critical"}


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

    def __post_init__(self) -> None:
        validate_status(self.status)
        validate_importance(self.importance)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexEntry":
        status = str(data.get("status", "inbox"))
        importance = str(data.get("importance", "normal"))
        validate_status(status)
        validate_importance(importance)
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
            confidence=float(data.get("confidence", 1.0)),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def __post_init__(self) -> None:
        validate_status(self.status)
        validate_importance(self.importance)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryMail":
        status = str(data.get("status", "inbox"))
        importance = str(data.get("importance", "normal"))
        validate_status(status)
        validate_importance(importance)
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
            confidence=float(data.get("confidence", 1.0)),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
            context=str(data.get("context", "")),
            decisions=[str(item) for item in data.get("decisions", [])],
            artifacts=[Artifact.from_dict(item) for item in data.get("artifacts", [])],
            next_actions=[str(item) for item in data.get("next_actions", [])],
            risks=[str(item) for item in data.get("risks", [])],
            source_refs=[SourceRef.from_dict(item) for item in data.get("source_refs", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        data["source_refs"] = [source_ref.to_dict() for source_ref in self.source_refs]
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
        )


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        allowed = ", ".join(sorted(VALID_STATUSES))
        raise ValueError(f"Invalid memory status {status!r}. Expected one of: {allowed}")


def validate_importance(importance: str) -> None:
    if importance not in VALID_IMPORTANCE:
        allowed = ", ".join(sorted(VALID_IMPORTANCE))
        raise ValueError(f"Invalid importance {importance!r}. Expected one of: {allowed}")
