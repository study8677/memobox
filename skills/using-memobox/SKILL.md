---
name: using-memobox
description: Use when a task mentions MemoBox, memory, recall, remember, project history, task history, decisions, evidence, or memory curation for an agent workflow.
---

# Using MemoBox

Use MemoBox as an index-first task memory layer through the existing `memobox` CLI. Do not assume an MCP server exists.

## Preconditions

- Confirm the `memobox` command is available with `command -v memobox`.
- If it is unavailable in a local checkout, use `PYTHONPATH=src python3 -m memobox.cli` from the MemoBox repository.
- Use the project store at `.memobox` unless the user gives another store.
- Use `${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}` as the global store.

## Workflow

1. At task start, use the `recall` skill or run:
   ```bash
   memobox --store .memobox recall "<query>" --project "<project>" --json
   ```
2. Read only index-level recall results first.
3. Open a memory body only when a recall result is relevant:
   ```bash
   memobox --store .memobox show <memory-id> --json
   ```
4. Open raw trace only when the user asks for evidence or the task requires proof:
   ```bash
   memobox --store .memobox raw <memory-id> --json
   ```
5. At task completion, use the `remember` skill to write one task-level Memory Mail.
6. For duplicates, stale memories, pinned memories, or global promotion, use the `curate` skill.

Keep summaries short, cite concrete files or commands in the body, and avoid storing secrets.
