---
name: curate
description: Use when the user asks to curate, deduplicate, merge, pin, archive, mark stale, promote, or clean up MemoBox memories.
---

# Curate MemoBox Memory

Use curation commands to keep an opted-in `.memobox` useful and lightweight. Review `.memobox/index.json` directly before modifying records. MemoBox may expose duplicate candidates, but the model or user makes every merge, stale, pin, archive, and promotion decision.

Do not initialize a missing store. Do not curate during simple or sensitive tasks unless the user explicitly asks. A weekly review during dogfooding is usually enough.

## Review Order

1. Read `.memobox/index.json` first.
2. Review `needs_review` records created by the `PreCompact(auto)` safety net; keep their durable content in a deliberate Memory Mail or archive/stale-mark the checkpoint.
3. Open candidate bodies before merging, marking stale, pinning, or promoting.
4. Prefer fewer high-value records over transcript-like accumulation.
5. Preserve `source_refs` such as `memobox:<id>` because they make real reuse measurable.

## Common Commands

Find likely duplicates:

```bash
memobox --store .memobox curate duplicates --json
```

Merge duplicates and archive the source memories:

```bash
memobox --store .memobox curate merge <id-a> <id-b> \
  --subject "<merged subject>" \
  --summary "<merged index summary>" \
  --json
```

Mark exact memory ids as stale after reviewing the index:

```bash
memobox --store .memobox status <id-a> stale
memobox --store .memobox status <id-b> stale
```

Pin exact memory ids after reviewing the index:

```bash
memobox --store .memobox status <id-a> pinned
memobox --store .memobox status <id-b> pinned
```

Promote reusable project memory into global memory only after confirming that the body is verified, portable beyond the current workspace, understandable without private repository context, and free of sensitive data:

```bash
memobox --store .memobox promote <memory-id> \
  --global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}" \
  --tag "<reusable-pattern>" \
  --json
```

Before merging, stale-marking, pinning, or promoting, read `.memobox/index.json` and summarize the exact ids you selected unless the user already gave exact ids and intent. The duplicates command is only a candidate list; it is not a relevance or merge decision.

Keep the global index intentionally small. Do not promote one-off project status, repository-specific paths, speculative conclusions, secrets, personal data, or confidential raw traces. When global knowledge is reused in a project, preserve it with `--source-ref "memobox-global:<id>"`.
