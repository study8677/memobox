# Contributing to MemoBox

Thanks for helping improve MemoBox.

## Good First Areas

- Improve agent integration examples.
- Add more retrieval backends.
- Design memory curator workflows.
- Improve schema validation and migration.
- Build MCP, Obsidian, or mem0 integrations.

## Development

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest -q
```

Before opening a PR:

- Keep README examples in both Chinese and English aligned.
- Add tests for behavior changes.
- Keep search index-first unless the change explicitly introduces an opt-in retrieval backend.
- Do not store full memory bodies or raw traces in `index.json`.

## Commit Style

Use short, direct commit messages, for example:

```text
Add MemoBox CI workflow
Improve README quick start
```

