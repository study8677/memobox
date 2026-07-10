---
name: write-memory
description: Use at the end of non-trivial work in an opted-in .memobox project only when the result passes the durable-memory worthiness gate, or when the user explicitly asks to save a memory.
---

# Write MemoBox Memory

Write a Memory Mail only for a durable, verified outcome. Store decisions and reusable evidence, not a transcript dump. An existing `.memobox` directory is the opt-in signal; do not create one automatically.

## Worthiness Gate

Write only when at least one of these is true:

- A durable decision, constraint, or project convention was established.
- A non-obvious cause was found and the fix was verified.
- Exact files, commands, URLs, or other artifacts will save meaningful investigation later.
- An unresolved risk or next action must survive the current session.
- The result is a useful cross-session or cross-agent handoff.

Write nothing when the task was a simple lookup, formatting or mechanical edit, contains sensitive material that cannot be safely excluded, produced only speculation, duplicates an existing memory, or has no likely persistent value. Do not create a record merely because the task ended or merely to log that another memory was opened.

## Steps

1. Keep one coherent durable outcome per record; most tasks should write zero or one record.
2. Create a concise subject and a one-sentence summary useful from the index alone.
3. Include verified context in `--body`; put decisions, artifacts, risks, and next actions in their structured flags.
4. Add one `--source-ref "memobox:<id>"` for each previously stored memory that materially influenced this result. Do not cite ids that were merely opened.
5. Confirm `command -v memobox`. In a MemoBox source checkout only, use `PYTHONPATH=src python3 -m memobox.cli` as the fallback.
6. Run, omitting empty flags:
   ```bash
   memobox --store .memobox write \
     --subject "<short title>" \
     --summary "<index-level summary>" \
     --project "<project>" \
     --team "<team>" \
     --role "<role>" \
     --tags "<comma,separated,tags>" \
     --body "<verified context and result>" \
     --decision "<decision worth preserving>" \
     --artifact "file:<exact path or evidence URI>" \
     --risk "<remaining caveat>" \
     --next-action "<follow-up if any>" \
     --source-ref "memobox:<reused-memory-id>" \
     --json
   ```
7. Confirm the returned id exists in `.memobox/mails/<id>.json`.

Never store secrets, credentials, private tokens, personal data, confidential raw content, or unredacted logs. Use `--raw-trace-file` only when the user explicitly wants the evidence retained and it has been checked for sensitive data.

`PreCompact(auto)` is a safety net, not the primary write path. Its `needs_review` checkpoints may be partial and should not replace a deliberate, structured end-of-task Memory Mail.
