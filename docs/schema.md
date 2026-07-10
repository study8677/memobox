# MemoBox Schema

MemoBox stores memory in three local file layers. Models read these files directly with Bash; the `memobox` CLI is only for writes and maintenance operations that need consistency.

`mails/*.json` is the durable source of truth. `index.json` is a derived, rebuildable directory. Store mutations are serialized across processes and replace body, trace, and index files atomically, so models never observe a partially written individual file. If a process stops between cross-file steps, `memobox verify` reports the inconsistency and `memobox rebuild-index` reconstructs the index from valid mail bodies without deleting user data.

## `index.json`

`index.json` is a JSON array of lightweight `IndexEntry` records.

Important fields:

- `schema_version`: integer schema version.
- `id`: memory mail id.
- `subject`: short title.
- `summary`: compact scan text for models.
- `project`, `workspace`, `team`, `role`: routing fields.
- `tags`, `participants`: routing, grouping, display, and model-selection signals.
- `importance`: `low`, `normal`, `high`, or `critical`.
- `status`: `inbox`, `pinned`, `archived`, `stale`, or `needs_review`.
- `confidence`: summary reliability from `0.0` to `1.0`.
- `created_at`, `updated_at`: UTC ISO 8601 timestamps.

The index must not contain full memory bodies, raw traces, or long evidence payloads.

## `mails/<id>.json`

The memory body extends index metadata with:

- `context`: expandable background and result.
- `decisions`: confirmed decisions.
- `artifacts`: files, URLs, PRs, deploys, reports, or other evidence.
- `next_actions`: remaining follow-up work.
- `risks`: known caveats.
- `source_refs`: references to raw trace, thread, or external evidence.

## `traces/<id>.jsonl`

Raw trace is optional JSONL. It can store conversation turns, tool calls, terminal evidence, or external event records.

Models should read `.memobox/index.json`, choose specific memory ids to open, then read `.memobox/mails/<id>.json` or `.memobox/traces/<id>.jsonl` directly only when needed.

## Integrity maintenance

```bash
memobox --store .memobox verify --json
memobox --store .memobox rebuild-index --json
```

`verify` never repairs or deletes records. `rebuild-index` replaces the derived index only when every mail body is valid; otherwise it returns a failure report and leaves the existing index untouched.
