---
name: recall
description: Use when starting a task or when the user asks to search, recall, inspect, or compare MemoBox project or global memories.
---

# Recall MemoBox Memory

Recall is index-first. Search project and global memory indexes before opening any body or raw trace.

## Steps

1. Build a short query from the current task, including project names, feature names, files, errors, or decisions.
2. Run:
   ```bash
   memobox --store .memobox recall "<query>" --project "<project>" --json
   ```
   Add `--global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}"` when the global path must be explicit.
3. Summarize matching index entries by id, subject, summary, project, tags, status, and scope.
4. Open a body only for relevant hits:
   ```bash
   memobox --store .memobox show <memory-id> --json
   ```
5. Do not open raw trace unless evidence is required:
   ```bash
   memobox --store .memobox raw <memory-id> --json
   ```

If the store is missing, initialize only when the user wants to start using MemoBox in that project. Otherwise report that no MemoBox store exists.
