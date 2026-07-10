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
- `supersedes`: optional list of older memory ids replaced by this record.
- `last_verified_at`: optional ISO 8601 date or timezone-aware datetime for the latest verification.
- `valid_until`: optional ISO 8601 date or timezone-aware datetime after which the memory should be reviewed.

The index must not contain full memory bodies, raw traces, or long evidence payloads.
The freshness fields are signals for the model; passing `valid_until` does not start a timer or automatically change status.

## `mails/<id>.json`

The memory body extends index metadata with:

- `context`: expandable background and result.
- `decisions`: confirmed decisions.
- `artifacts`: files, URLs, PRs, deploys, reports, or other evidence.
- `next_actions`: remaining follow-up work.
- `risks`: known caveats.
- `source_refs`: references to raw trace, thread, or external evidence.

When `memobox write --supersedes <id>` is used, every referenced id must already exist in the same store. The store rejects missing ids and self-references, adds a `memobox` source reference from the new record back to each replaced record, and marks each replaced record `stale` while holding the store lock. Repeat `--supersedes` to replace more than one record.

When a project memory is promoted, the global copy adds a provenance reference containing the absolute project-store path and source id. Promotion copies freshness signals but not the source store's `supersedes` ids, because those ids are scoped to the source store.

```bash
memobox --store .memobox write \
  --subject "Current deployment procedure" \
  --summary "Verified replacement for the old deployment note." \
  --supersedes old-deployment-memory-id \
  --last-verified-at 2026-07-10T17:30:00+08:00 \
  --valid-until 2026-10-10
```

Schema v2 adds these three optional fields. Existing schema v1 JSON remains readable and rebuildable; absent fields mean that no supersession or freshness metadata was recorded. Date-only values use `YYYY-MM-DD`. Datetimes must include a timezone offset or `Z` suffix.

Freshness values are storage signals: MemoBox validates their syntax but does not compare `last_verified_at` with `valid_until` or infer expiry status. Promotion copies the freshness values, but not `supersedes`, because those ids belong to the source store; the promoted record keeps its project-origin `source_ref` instead.

## `traces/<id>.jsonl`

Raw trace is optional JSONL. It can store conversation turns, tool calls, terminal evidence, or external event records.

Models should read `.memobox/index.json`, choose specific memory ids to open, then read `.memobox/mails/<id>.json` or `.memobox/traces/<id>.jsonl` directly only when needed.

## Integrity maintenance

```bash
memobox --store .memobox verify --json
memobox --store .memobox rebuild-index --json
```

`verify` never repairs or deletes records. `rebuild-index` replaces the derived index only when every mail body is valid; otherwise it returns a failure report and leaves the existing index untouched.
