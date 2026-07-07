# Contributing to MemoBox

Thanks for helping improve MemoBox.

## Good First Areas

- Improve model/tool integration examples.
- Improve index directory organization.
- Design memory maintenance flows.
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
- Keep memory storage index-first; the model chooses whether and which ids to open.
- Do not store full memory bodies or raw traces in `index.json`.

## Commit Style

Use short, direct commit messages, for example:

```text
Add MemoBox CI check
Improve README quick start
```
