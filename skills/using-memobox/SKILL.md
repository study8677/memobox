---
name: using-memobox
description: Use automatically for non-trivial work when the current project already contains .memobox, or when the user explicitly asks to read, write, or maintain MemoBox memory.
---

# Using MemoBox

Use MemoBox as an opt-in, index-first local file protocol. Read `.memobox` JSON files directly with Bash; use the `memobox` CLI only for writing and maintenance. MemoBox exposes memory structure. It does not rank memories, decide relevance, or orchestrate the task.

## Activation Contract

- An existing `.memobox` directory is the project's opt-in signal. Do not initialize one merely because the plugin is installed.
- At the start of every non-trivial task in an opted-in project, inspect `.memobox/index.json` before broad investigation.
- Skip the MemoBox loop for simple lookups, formatting, one-line or mechanical edits, and tasks with no likely cross-session value.
- Skip MemoBox for security-restricted or sensitive work unless the user explicitly authorizes safe, redacted persistence. Never persist secrets, credentials, tokens, personal data, or confidential raw content.
- If `.memobox` is absent, continue the task without MemoBox. Initialize it only when the user explicitly opts in.

## Start-Of-Task Read Loop

1. Confirm the project is opted in and read the index:
   ```bash
   test -d .memobox && cat .memobox/index.json
   ```
2. Let the model inspect subjects, summaries, tags, status, and timestamps and choose which ids, if any, merit opening. MemoBox makes no relevance decision.
3. Read only the chosen bodies:
   ```bash
   cat .memobox/mails/<memory-id>.json
   ```
4. Read raw trace only when the task requires source evidence:
   ```bash
   cat .memobox/traces/<memory-id>.jsonl
   ```
5. Track `opened_memory_ids` separately from `reused_memory_ids`. A memory counts as reused only if it materially changes the plan, decision, implementation, or verification.
6. Read the global index only when the user or task explicitly calls for cross-project experience:
   ```bash
   cat "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}/index.json"
   ```

## End-Of-Task Write Loop

1. Apply a strict worthiness gate. Write only a durable decision or constraint, a non-obvious cause and verified fix, reusable evidence or exact artifacts, an important unresolved risk, or a cross-session handoff.
2. Write zero records when the task was simple, sensitive, speculative, already captured, or produced no durable insight. Do not write merely because the task ended or merely to record usage.
3. Keep one coherent durable outcome per record; most tasks should produce zero or one record.
4. Before writing, confirm the CLI is available with `command -v memobox`. In a MemoBox source checkout only, the fallback is `PYTHONPATH=src python3 -m memobox.cli`.
5. Use structured fields instead of a transcript dump:
   ```bash
   memobox --store .memobox write \
     --subject "<short title>" \
     --summary "<index-level summary>" \
     --project "<project>" \
     --body "<verified context and outcome>" \
     --decision "<durable decision>" \
     --artifact "file:<exact path or evidence URI>" \
     --risk "<remaining caveat>" \
     --next-action "<unfinished follow-up>" \
     --source-ref "memobox:<reused-memory-id>" \
     --json
   ```
   Repeat `--source-ref "memobox:<id>"` for every materially reused memory. Omit fields that do not apply.
6. Confirm the returned id exists in `.memobox/mails/<id>.json`.

## PreCompact Is Only A Safety Net

`PreCompact(auto)` may write a conservative `needs_review` checkpoint when `.memobox` already exists. By default it stores selected metadata and git state, not the full hook payload. It may not receive the full transcript and must not replace the deliberate end-of-task write loop. Curate or archive checkpoint records after review. Set `MEMOBOX_PRECOMPACT_DISABLED=1` for sensitive sessions, `MEMOBOX_PRECOMPACT_INCLUDE_PAYLOAD=1` only with explicit approval, and `MEMOBOX_PRECOMPACT_INIT=1` only when the user explicitly wants automatic store creation.
