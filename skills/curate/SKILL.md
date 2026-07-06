---
name: curate
description: Use when the user asks to curate, deduplicate, merge, pin, archive, mark stale, promote, or clean up MemoBox memories.
---

# Curate MemoBox Memory

Use curation commands to keep `.memobox` useful and lightweight. Prefer index-level operations first.

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

Mark stale matches:

```bash
memobox --store .memobox curate stale "<query>" --project "<project>" --json
```

Pin important matches:

```bash
memobox --store .memobox curate pin "<query>" --project "<project>" --json
```

Promote reusable project memory into global memory:

```bash
memobox --store .memobox promote <memory-id> \
  --global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}" \
  --tag "<reusable-pattern>" \
  --json
```

Before merging, stale-marking, or promoting, show the candidate ids and summarize what will change unless the user already gave exact ids and intent.
