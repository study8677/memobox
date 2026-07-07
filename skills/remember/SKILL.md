---
name: write-memory
description: Use when the model chooses to save, record, persist, or write a MemoBox memory.
---

# Write MemoBox Memory

Write one Memory Mail when there is useful context to preserve. Store decisions and useful context, not a transcript dump.

## Steps

1. Create a concise subject that names the memory.
2. Write a one-sentence summary that is useful from the index alone.
3. Include project, team, role, and tags when known.
4. Put details, rationale, files changed, commands run, risks, and follow-ups in the body or structured flags.
5. Run:
   ```bash
   memobox --store .memobox write \
     --subject "<short title>" \
     --summary "<index-level summary>" \
     --project "<project>" \
     --team "<team>" \
     --role "<role>" \
     --tags "<comma,separated,tags>" \
     --body "<rationale, useful context, files, commands, evidence pointers>" \
     --decision "<decision worth preserving>" \
     --next-action "<follow-up if any>"
   ```

Do not store secrets, credentials, private tokens, or raw logs unless the user explicitly asks and the data is safe to keep. Use `--raw-trace-file` only for evidence that should be retained.
