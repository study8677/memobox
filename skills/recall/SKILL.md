---
name: index-memory
description: Use when the model chooses to inspect MemoBox project or global memory index files.
---

# Inspect MemoBox Memory Index

MemoBox exposes a local file protocol without deciding relevance. The model chooses whether to inspect the index file, which ids to read, and whether trace evidence is needed.

## Steps

1. Read the project index file:
   ```bash
   cat .memobox/index.json
   ```
   Read the global index too only when explicitly useful:
   ```bash
   cat "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}/index.json"
   ```
2. Read the returned index entries. They include ids, subjects, summaries, tags, status, and timestamps.
3. Decide which memory ids are worth opening.
4. Read a body only for ids you choose:
   ```bash
   cat .memobox/mails/<memory-id>.json
   ```
5. Do not read raw trace unless evidence is required:
   ```bash
   cat .memobox/traces/<memory-id>.jsonl
   ```

If the store is missing, initialize only when the user wants to start using MemoBox in that project. Otherwise report that no MemoBox store exists.
