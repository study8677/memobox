---
name: remember
description: Use when finishing a task or when the user asks to save, record, remember, persist, or write a MemoBox memory.
---

# Remember Task Outcomes

Write one task-level Memory Mail after meaningful work is complete. Store decisions and useful context, not a transcript dump.

## Steps

1. Create a concise subject that names the task outcome.
2. Write a one-sentence summary that is useful from the index alone.
3. Include project, team, role, and tags when known.
4. Put details, rationale, files changed, commands run, risks, and follow-ups in the body or structured flags.
5. Run:
   ```bash
   memobox --store .memobox remember \
     --subject "<short outcome>" \
     --summary "<index-level summary>" \
     --project "<project>" \
     --team "<team>" \
     --role "memory-curator" \
     --tags "<comma,separated,tags>" \
     --body "<task outcome, rationale, useful context>" \
     --decision "<decision worth preserving>" \
     --next-action "<follow-up if any>"
   ```

Do not store secrets, credentials, private tokens, or raw logs unless the user explicitly asks and the data is safe to keep. Use `--raw-trace-file` only for evidence that should be retained.
