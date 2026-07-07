# MemoBox Schema

MemoBox stores memory in three layers.

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

Models can read the index directory, choose specific memory ids to open, and read raw trace only when the selected body is insufficient.
