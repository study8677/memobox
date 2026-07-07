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

Mark exact memory ids as stale after reviewing the index:

```bash
memobox --store .memobox curate stale <id-a> <id-b> --json
```

Pin exact memory ids after reviewing the index:

```bash
memobox --store .memobox curate pin <id-a> <id-b> --json
```

Promote reusable project memory into global memory:

```bash
memobox --store .memobox promote <memory-id> \
  --global-store "${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}" \
  --tag "<reusable-pattern>" \
  --json
```

Before merging, stale-marking, pinning, or promoting, review the index directory and summarize the exact ids you selected unless the user already gave exact ids and intent.
