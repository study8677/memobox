<div align="center">

# MemoBox

**A model-readable memory store for AI agents.**

Give models a local-first memory store they can inspect with Bash: index first, body and evidence only when they choose.

[中文](README.md) · [Schema](docs/schema.md) · [Example](examples/demo.py) · [GitHub](https://github.com/study8677/memobox)

[![CI](https://github.com/study8677/memobox/actions/workflows/ci.yml/badge.svg)](https://github.com/study8677/memobox/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

<br/>

<img src="docs/assets/memobox-flow.svg" alt="MemoBox index-first memory store" width="860">

</div>

---

## What Is MemoBox

MemoBox is a **model-readable memory store**. It stores useful work records as structured memory mail and exposes three layers: lightweight index, expandable body, and raw evidence.

It targets a common long-term memory problem for engineering models:

> We do not lack history. We lack a model-readable, auditable surface that can be expanded on demand.

MemoBox keeps the boundary simple:

```text
MemoBox manages memory storage -> the model decides whether to call it -> the model decides whether to read index, body, or evidence
```

## Why Mailbox

The mailbox model is not decorative. It is the core interaction model:

- **The subject is the best summary**: email subjects are short, explicit, and scannable; `MemoryMail.subject` is the model-friendly first layer.
- **The inbox is the lightweight index**: `index.json` is a scannable directory, but MemoBox does not decide relevance.
- **The body is progressive disclosure**: if the model needs more context, it can read the selected `mails/<id>.json` body.
- **Attachments and originals are evidence**: `traces/<id>.jsonl` opens only when evidence is needed.
- **Status is memory lifecycle**: `pinned`, `archived`, `stale`, and `needs_review` map to inbox-style memory management.

This matches how models use Bash and tools: the storage layer exposes a clear surface, and the model decides when to read, which ids to read, and how deep to go.

MemoBox turns long model-visible history into progressive disclosure:

```text
subject -> summary -> memory body -> raw evidence
```

The first version focuses on four promises:

- **Index-first**: expose the `index.json` directory before full bodies and evidence.
- **Memory mail**: store decisions, artifacts, risks, and next actions as structured memory records.
- **Evidence-aware**: open `Memory Mail` or `Raw Trace` only when more evidence is needed.
- **Local-first Python**: zero runtime dependencies, CLI + Python API, auditable JSON files.

## 30-Second Demo

```bash
memobox --store .memobox write \
  --subject "Fix slow /orders API" \
  --summary "Found N+1 query pattern and added eager loading." \
  --project api-platform \
  --team backend \
  --role model \
  --tags performance,n-plus-one \
  --body "Changed OrderService query path and added regression test." \
  --decision "Prefer query-level fix before introducing cache."

memobox --store .memobox index --json
```

The first layer a model can read is not full history, but a compact directory entry:

```json
{
  "subject": "Fix slow /orders API",
  "summary": "Found N+1 query pattern and added eager loading.",
  "project": "api-platform",
  "tags": ["performance", "n-plus-one"],
  "status": "inbox"
}
```

MemoBox does not decide relevance. The model decides whether to read a body or raw trace.

## Not Another Vector Memory Store

| Common memory systems | MemoBox |
| --- | --- |
| User preferences, facts, semantic fragments | Work records, decisions, evidence, next actions |
| Often embedding-first | Directory-first by default, explainable and auditable |
| Source chains can be unclear | Summary -> body -> raw trace |
| Great for personal assistant preferences | Great for engineering models and tool-driven sessions |
| More history can become more black-box | Auditable index, pin, archive, mark stale |

MemoBox can work with mem0, RAG, Obsidian, and logs. mem0 is better for user preferences and factual memory; MemoBox is better for model-readable work records.

## Features

| Feature | What it means |
| --- | --- |
| Index-first store | `index` lists the `index.json` directory without opening bodies or traces |
| Memory mail | Important work records become expandable memory records |
| Raw trace on demand | Conversation/tool/terminal evidence opens only when requested |
| Team-ready metadata | Built-in `project`, `workspace`, `team`, `role`, `participants` |
| Memory maintenance | `pinned`, `needs_review`, `archived`, `stale` |
| Local-first CLI | Pure Python and JSON files, callable through Bash |

## Architecture

```mermaid
flowchart LR
    A["Model decides to inspect memory"] --> B["Read MemoBox Index<br/>index.json"]
    B --> C{"Need a body?"}
    C -- "No" --> D["Continue with index-level context"]
    C -- "Yes" --> E["Read Memory Mail<br/>mails/&lt;id&gt;.json"]
    E --> F{"Need evidence?"}
    F -- "No" --> G["Use body context"]
    F -- "Yes" --> H["Read Raw Trace<br/>traces/&lt;id&gt;.jsonl"]
```

| Layer | File | Contents |
| --- | --- | --- |
| MemoBox Index | `index.json` | subject, summary, project, team, role, tags, status, timestamps |
| Memory Mail | `mails/<id>.json` | context, decisions, artifacts, risks, next actions, source refs |
| Raw Trace | `traces/<id>.jsonl` | conversation turns, tool calls, terminal evidence, external events |

The test suite verifies directory reads return only index-level data and do not open mail bodies or raw traces.

## Quick Start

```bash
git clone https://github.com/study8677/memobox.git
cd memobox
python3 -m pip install -e ".[test]"
```

Initialize:

```bash
memobox --store .memobox init
```

Add memory:

```bash
memobox --store .memobox write \
  --subject "MemoBox index-first storage" \
  --summary "Models can read the lightweight index before opening memory bodies." \
  --project memobox \
  --team platform \
  --role model \
  --tags memory,storage,index-first \
  --body "Implemented index/body/raw-trace split and tests for lazy expansion." \
  --decision "Directory reads must never open raw traces by default."
```

Read the memory index:

```bash
memobox --store .memobox index --json
```

Read body:

```bash
memobox --store .memobox read <memory-id> --json
```

Read raw trace:

```bash
memobox --store .memobox trace <memory-id> --json
```

## Python API

```python
from memobox import JsonMemoBoxStore, MemoryMail

store = JsonMemoBoxStore(".memobox")

store.add_mail(
    MemoryMail(
        id="",
        subject="Memory storage design",
        summary="MemoBox stores model-readable memory as index-first mail records.",
        project="memobox",
        team="platform",
        role="model",
        tags=["memory-store", "index-first"],
        context="Longer expandable body lives outside the index.",
        decisions=["Expose storage structure and let the model decide what to read."],
    )
)

directory = store.list_index()
mail = store.open_mail(directory[0].id)
```

## Storage Interface

MemoBox exposes a storage interface, not an orchestration layer. A model with Bash/tool access can decide whether to call these commands.

| Command | Purpose |
| --- | --- |
| `memobox write` | Write one Memory Mail record |
| `memobox index` | List lightweight memory index records |
| `memobox read <id>` | Read one memory body |
| `memobox trace <id>` | Read raw trace evidence |
| `memobox status <id> <status>` | Update memory status |
| `memobox promote <id>` | Copy reusable memory into a global store |
| `memobox curate ...` | Deduplicate, merge, pin, and mark stale |

Recommended project/global layout:

```text
your-project/.memobox        # current project memory
~/.memobox-global            # reusable cross-project memory
```

You can also set the global store with an environment variable:

```bash
export MEMOBOX_GLOBAL_STORE="$HOME/.memobox-global"
```

Read the current project index:

```bash
memobox --store .memobox index --json
```

Explicitly read project and global indexes:

```bash
memobox --store .memobox index \
  --global-store ~/.memobox-global \
  --json
```

Write one memory:

```bash
memobox --store .memobox write \
  --subject "Improve MemoBox README positioning" \
  --summary "Reframed MemoBox as a model-readable memory store instead of orchestration." \
  --project memobox \
  --team platform \
  --role model \
  --tags readme,storage,open-source \
  --body "The public surface now leads with write/index/read/trace storage commands." \
  --decision "Keep MemoBox out of relevance ranking and orchestration."
```

The Python API keeps the same boundary:

```python
def list_memobox_index() -> str:
    entries = store.list_index()
    return "\n".join(f"{entry.id}: {entry.subject} - {entry.summary}" for entry in entries)


def open_memory_mail(memory_id: str) -> str:
    mail = store.open_mail(memory_id)
    return mail.context


def open_raw_trace(memory_id: str) -> list[dict]:
    return store.open_raw_trace(memory_id)
```

Promote reusable project memory:

```bash
memobox --store .memobox promote <memory-id> \
  --global-store ~/.memobox-global \
  --tag readme-pattern
```

Curate memory:

```bash
memobox --store .memobox curate duplicates --json
memobox --store .memobox curate merge <id-a> <id-b> \
  --subject "Merged README homepage guidance" \
  --summary "Merged duplicate README optimization memories."
memobox --store .memobox curate stale <id>
memobox --store .memobox curate pin <id>
```

## Claude Code / Codex Plugin

The first MemoBox plugin is a **skills-only plugin**. It does not start an MCP server or change CLI arguments. It exposes the existing `memobox` storage commands to Claude Code and Codex.

Install the CLI first:

```bash
python3 -m pip install --user git+https://github.com/study8677/memobox.git
```

Install in Claude Code:

```bash
claude plugin marketplace add study8677/memobox
claude plugin install memobox@memobox-marketplace --scope user
```

Install in Codex:

```bash
codex plugin marketplace add study8677/memobox
codex plugin add memobox@memobox-marketplace
```

After installation, use natural language:

```text
Use MemoBox to inspect this project's memory index.
Use MemoBox to write one memory.
Use MemoBox to curate duplicate memories.
```

Or invoke skills explicitly:

```text
Claude Code: /memobox:using-memobox
Codex: $using-memobox
```

Defaults:

- Project memory: `.memobox` in the current repository
- Global memory: `${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}`
- MemoBox exposes index, body, and evidence layers; the model decides whether to call it and how deep to read.

## Who It Is For

- Coding models that need project decisions, paths, failures, and fixes.
- Ops models that need incident notes, command evidence, and rollback steps.
- Research models that need claims, sources, and open hypotheses.
- Multi-tool collaboration that shares structured work records instead of chat transcripts.
- Knowledge-base users turning conversation history into maintainable work records.

## Roadmap

**Storage**

- [x] Local JSON store
- [ ] SQLite backend
- [ ] Schema migration

**Storage Interface**

- [x] Index-first storage directory
- [x] Neutral CLI: `write`, `index`, `read`, `trace`
- [ ] Better index organization and lifecycle views

**Model Integration**

- [x] CLI: `init`, `write`, `index`, `read`, `trace`, `status`, `promote`, `curate`
- [x] Claude Code / Codex skills-only plugin
- [ ] MCP server for Codex, Claude Desktop, Cursor

**UX / Trust**

- [x] Chinese and English README files
- [ ] Privacy redaction hooks
- [ ] Web UI for inbox-style model-readable memory
- [ ] Social preview and visual identity

## Development

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest -q
PYTHONPATH=src python3 examples/demo.py
```

## What Is Tested

MemoBox's core promise is index-first directory review, so tests verify both output and read path:

- `index` calls `list_index()` only.
- Directory output does not include `context`, `decisions`, or raw trace contents.
- `read` expands `Memory Mail`.
- `trace` opens `Raw Trace`.

## Contributing

MemoBox is alpha-stage. Good contribution areas:

- Model-readable memory evaluation datasets.
- mem0 / MCP / Obsidian integrations.
- Better index organization, stale-memory, and archive policies.
- Team permission and audit models.
- Web UI and social preview design.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE).
