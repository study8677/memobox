---
name: index-memory
description: Use when the model chooses to inspect MemoBox project or global memory indexes.
---

# Inspect MemoBox Memory Index

MemoBox exposes storage structure without deciding relevance. The model chooses whether to inspect the index, which ids to read, and whether trace evidence is needed.

## Steps

1. Run:
   ```bash
   memobox --store .memobox index --json
   ```
   Add `--global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}"` when the model explicitly wants the global store too.
2. Read the returned index directories. They include ids, subjects, summaries, tags, status, timestamps, and body/raw trace locations.
3. Decide which memory ids are worth opening.
4. Read a body only for ids you choose:
   ```bash
   memobox --store .memobox read <memory-id> --json
   ```
5. Do not read raw trace unless evidence is required:
   ```bash
   memobox --store .memobox trace <memory-id> --json
   ```

If the store is missing, initialize only when the user wants to start using MemoBox in that project. Otherwise report that no MemoBox store exists.
