---
name: index-memory
description: Use at the start of non-trivial work when the current project already contains .memobox, or when the user explicitly asks to inspect a MemoBox index.
---

# Inspect MemoBox Memory Index

MemoBox exposes a local file protocol without deciding relevance. An existing `.memobox` directory is project opt-in. The model reads the index, chooses which ids to open, and decides whether trace evidence is needed.

Skip this skill for simple tasks, tasks with no likely persistent value, and security-restricted or sensitive work unless the user explicitly authorizes safe use. If `.memobox` is absent, continue without MemoBox and do not initialize it automatically.

## Steps

1. At the start of a non-trivial task, read the project index before broad investigation:
   ```bash
   test -d .memobox && cat .memobox/index.json
   ```
2. Read the returned index entries. They include ids, subjects, summaries, tags, status, and timestamps.
3. Decide which memory ids, if any, are worth opening. This is the model's judgment; MemoBox does not rank, filter, or select them.
4. Read a body only for ids you choose:
   ```bash
   cat .memobox/mails/<memory-id>.json
   ```
5. Do not read raw trace unless evidence is required:
   ```bash
   cat .memobox/traces/<memory-id>.jsonl
   ```
6. Keep two task-local lists:
   - `opened_memory_ids`: bodies inspected.
   - `reused_memory_ids`: memories that materially changed the plan, decision, implementation, or verification.
7. If the task produces a new high-value Memory Mail, pass each reused project id as `--source-ref "memobox:<id>"`. Merely opening a memory does not make it reused, and reuse alone is not a reason to create a new record.
8. Read the global index when cross-project experience is explicit, the project index has no useful record for a repeatable task, or the task is likely to reuse portable setup, authentication, CI, deployment, plugin, toolchain, or incident knowledge:
   ```bash
   test -f "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}/index.json" && \
     cat "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}/index.json"
   ```
9. Track `opened_global_memory_ids` separately from `reused_global_memory_ids`. Read only selected global bodies, and cite a materially reused global record as `--source-ref "memobox-global:<id>"` if the task produces a new Memory Mail.

If the store is missing, initialize only when the user explicitly wants to start using MemoBox in that project.
