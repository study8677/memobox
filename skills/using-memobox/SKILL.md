---
name: using-memobox
description: Use when the model chooses to inspect MemoBox memory files or write and maintain MemoBox records.
---

# Using MemoBox

Use MemoBox as an index-first, model-readable local file protocol. Read `.memobox` JSON files directly with Bash; use the `memobox` CLI only for writing and maintenance. Do not assume an MCP server exists.

## Preconditions

- Confirm the `memobox` command is available with `command -v memobox`.
- If it is unavailable in a local checkout, use `PYTHONPATH=src python3 -m memobox.cli` from the MemoBox repository.
- Use the project store at `.memobox` unless the user gives another store.
- Use `${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}` as the global store.

## File Protocol And Commands

1. When memory may help, inspect the local index file:
   ```bash
   cat .memobox/index.json
   ```
   If the global store is explicitly useful, also run:
   ```bash
   cat "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}/index.json"
   ```
2. Use subjects, summaries, tags, status, and timestamps to decide which ids to open.
3. Read a memory body only for chosen ids:
   ```bash
   cat .memobox/mails/<memory-id>.json
   ```
4. Read raw trace only when evidence is required:
   ```bash
   cat .memobox/traces/<memory-id>.jsonl
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
