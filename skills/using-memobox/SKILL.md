---
name: using-memobox
description: Use when the model chooses to inspect, read, write, or maintain MemoBox memory records through Bash.
---

# Using MemoBox

Use MemoBox as an index-first, model-readable memory store through the existing `memobox` CLI. Do not assume an MCP server exists.

## Preconditions

- Confirm the `memobox` command is available with `command -v memobox`.
- If it is unavailable in a local checkout, use `PYTHONPATH=src python3 -m memobox.cli` from the MemoBox repository.
- Use the project store at `.memobox` unless the user gives another store.
- Use `${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}` as the global store.

## Storage Commands

1. When memory may help, inspect the index:
   ```bash
   memobox --store .memobox index --json
   ```
   Add `--global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}"` only when the model explicitly wants the global store too.
2. Use subjects, summaries, tags, status, timestamps, and body/raw trace paths to decide which ids to read.
3. Read a memory body only for chosen ids:
   ```bash
   memobox --store .memobox read <memory-id> --json
   ```
4. Read raw trace only when evidence is required:
   ```bash
   memobox --store .memobox trace <memory-id> --json
   ```
5. Write one memory record when there is useful context to preserve:
   ```bash
   memobox --store .memobox write \
     --subject "<short title>" \
     --summary "<index-level summary>" \
     --project "<project>" \
     --body "<useful context, decisions, artifacts, risks, follow-ups>"
   ```
6. For duplicates, stale memories, pinned memories, or global promotion, use `curate`, `status`, or `promote`.

Keep summaries short, cite concrete files or commands in the body, and avoid storing secrets.
