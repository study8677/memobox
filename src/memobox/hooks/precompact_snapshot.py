from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from memobox.models import MemoryMail, SourceRef
from memobox.store import JsonMemoBoxStore

SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|cookie|credential|password|refresh[_-]?token|secret|token)",
    re.IGNORECASE,
)
SECRET_TEXT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|cookie|password|refresh[_-]?token|secret|token)\b"
    r"\s*[:=]\s*([^\s,;}\]]+)"
)
MAX_TEXT_VALUE = 4000


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="memobox-precompact-snapshot",
        description="Write a MemoBox checkpoint before Codex compacts thread context.",
    )
    parser.add_argument("--store", default=os.environ.get("MEMOBOX_STORE", ".memobox"))
    parser.add_argument("--project", default="")
    parser.add_argument("--trigger", default="")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create the MemoBox store when it does not already exist.",
    )
    args = parser.parse_args(argv)

    cwd = Path.cwd()
    store_root = Path(args.store).expanduser()
    if not store_root.is_absolute():
        store_root = cwd / store_root

    if not store_root.exists() and not (args.init or env_truthy("MEMOBOX_PRECOMPACT_INIT")):
        print(f"memobox precompact hook skipped: store not found at {store_root}", file=sys.stderr)
        return 0

    raw_stdin = sys.stdin.read() if stdin_text is None else stdin_text
    payload = parse_payload(raw_stdin)
    sanitized_payload = sanitize(payload)
    trigger = args.trigger or find_payload_value(payload, ["trigger", "reason", "compact_trigger"]) or "unknown"
    thread_ref = find_payload_value(payload, ["thread_id", "threadId", "session_id", "conversationId", "conversation_id"])
    git = git_snapshot(cwd)
    project = args.project or find_payload_value(payload, ["project", "repository", "repo"]) or cwd.name

    store = JsonMemoBoxStore(store_root)
    mail = MemoryMail(
        id="",
        subject=f"Codex pre-compact checkpoint ({trigger})",
        summary=f"Codex PreCompact hook fired before {trigger} context compaction in {project}.",
        project=project,
        workspace=str(cwd),
        team="",
        role="codex-hook",
        tags=["codex", "precompact", "context", "checkpoint"],
        status="needs_review",
        context=build_context(trigger, cwd, git, sanitized_payload),
        decisions=[],
        next_actions=["Review this automatic checkpoint and promote or archive it."],
        risks=[
            "Hook payload content depends on the Codex host version.",
            "Full transcript capture is not guaranteed unless Codex includes it in the hook input.",
        ],
        source_refs=[SourceRef(kind="codex-hook", ref=str(thread_ref or "precompact"), note="PreCompact hook payload")],
    )
    stored = store.add_mail(
        mail,
        raw_trace=[
            {
                "event": "codex_precompact",
                "trigger": trigger,
                "cwd": str(cwd),
                "payload": sanitized_payload,
                "git": git,
            }
        ],
    )
    print(stored.id)
    return 0


def parse_payload(raw_stdin: str) -> dict[str, Any]:
    text = raw_stdin.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": trim_text(text), "format": "text"}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SECRET_KEY_RE.search(key_text):
                sanitized[key_text] = "[REDACTED]"
            else:
                sanitized[key_text] = sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return trim_text(SECRET_TEXT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value))
    return value


def trim_text(value: str) -> str:
    if len(value) <= MAX_TEXT_VALUE:
        return value
    return f"{value[:MAX_TEXT_VALUE]}...[truncated]"


def find_payload_value(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def git_snapshot(cwd: Path) -> dict[str, str]:
    return {
        "branch": run_git(cwd, ["branch", "--show-current"]),
        "head": run_git(cwd, ["rev-parse", "--short", "HEAD"]),
        "status": run_git(cwd, ["status", "--short"]),
    }


def run_git(cwd: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def build_context(trigger: str, cwd: Path, git: dict[str, str], payload: dict[str, Any]) -> str:
    lines = [
        "Codex PreCompact hook fired before context compaction.",
        "",
        f"Trigger: {trigger}",
        f"Workspace: {cwd}",
    ]
    if git.get("branch"):
        lines.append(f"Git branch: {git['branch']}")
    if git.get("head"):
        lines.append(f"Git HEAD: {git['head']}")
    lines.append(f"Git status: {git.get('status') or 'clean or unavailable'}")

    selected = selected_payload_fields(payload)
    if selected:
        lines.extend(["", "Hook payload fields:"])
        for key, value in selected.items():
            lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "This checkpoint is automatic and marked needs_review.",
            "It records hook metadata and local repository state.",
            "It does not guarantee full transcript capture unless Codex includes transcript content in the hook input.",
        ]
    )
    return "\n".join(lines)


def selected_payload_fields(payload: dict[str, Any]) -> dict[str, str]:
    keys = [
        "trigger",
        "reason",
        "thread_id",
        "threadId",
        "session_id",
        "conversationId",
        "conversation_id",
        "model",
        "cwd",
    ]
    selected: dict[str, str] = {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)):
            selected[key] = str(value)
    return selected


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
