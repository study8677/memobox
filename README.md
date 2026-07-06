# MemoBox

MemoBox is a task-level memory system for agents. It treats each finished task like a memory email: agents scan a lightweight MemoBox index first, then open the full memory body or raw trace only when needed.

## Storage Model

MemoBox has three layers:

- `index.json`: lightweight MemoBox index. Contains routing/search fields only: subject, summary, project, workspace, team, role, tags, participants, status, importance, confidence, and timestamps.
- `mails/<id>.json`: expandable task memory body. Contains context, decisions, artifacts, next actions, risks, and source refs.
- `traces/<id>.jsonl`: optional raw trace. This is never required for normal search.

Supported statuses:

- `inbox`
- `pinned`
- `archived`
- `stale`
- `needs_review`

By default, search includes `inbox`, `pinned`, and `needs_review`. Use `--all-statuses` when archived or stale memory should be considered.

## CLI

From the source checkout, either install the package:

```bash
python3 -m pip install -e .
memobox --store .memobox init
```

Or run without installing:

```bash
PYTHONPATH=src python3 -m memobox.cli --store .memobox init
```

Add one task-level memory mail:

```bash
memobox --store .memobox add \
  --subject "Agent memobox system" \
  --summary "Index-first task memory for agents." \
  --project agent-memory \
  --team platform \
  --role main-agent \
  --tags memory,memobox \
  --body "Expandable implementation details live here." \
  --decision "Use task-level memory mails."
```

Search the index only:

```bash
memobox --store .memobox search "memobox memory" --json
```

Open the full memory body:

```bash
memobox --store .memobox show <memory-id> --json
```

Open raw trace explicitly:

```bash
memobox --store .memobox raw <memory-id> --json
```

Archive or review memory:

```bash
memobox --store .memobox status <memory-id> archived
```

## Agent Read Flow

1. Extract request terms such as project, paths, people, and time hints.
2. Call `MemoBoxSearcher.search(...)`.
3. Inspect only returned index entries.
4. Open selected mails with `JsonMemoBoxStore.open_mail(id)`.
5. Open raw trace with `JsonMemoBoxStore.open_raw_trace(id)` only when evidence is insufficient.

The tests include a spy store that fails if search opens mail bodies or raw traces.
