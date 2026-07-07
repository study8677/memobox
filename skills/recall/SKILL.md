---
name: recall
description: Use when starting a task or when the user asks to inspect MemoBox project or global memory inboxes.
---

# Recall MemoBox Memory

Recall is index-first directory review. Open project and global memory inboxes before opening any body or raw trace. MemoBox exposes structure; the model chooses which ids to open.

## Steps

1. Run:
   ```bash
   memobox --store .memobox recall "<task context>" --project "<project>" --json
   ```
   Add `--global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}"` when the global path must be explicit.
2. Read the returned project/global index directories. They include ids, subjects, summaries, tags, status, timestamps, and body/raw trace locations.
3. Decide yourself which memory ids are worth opening for the task.
4. Open a body only for ids you choose:
   ```bash
   memobox --store .memobox show <memory-id> --json
   ```
5. Do not open raw trace unless evidence is required:
   ```bash
   memobox --store .memobox raw <memory-id> --json
   ```

If the store is missing, initialize only when the user wants to start using MemoBox in that project. Otherwise report that no MemoBox store exists.
