# Changelog

## Unreleased

- Reframed MemoBox as an index-first local file protocol for AI agents.
- Removed CLI read wrappers and legacy aliases: `index`, `read`, `trace`, `add`, `inbox`, `map`, `show`, `raw`, `recall`, and `remember`.
- Kept the CLI focused on writes and maintenance: `init`, `write`, `status`, `promote`, and `curate`.
- Updated docs, skills, and plugin metadata to read `.memobox/index.json`, `mails/*.json`, and `traces/*.jsonl` directly with Bash.

## 0.1.0

- Initial MemoBox package.
- Added model-readable memory mail model.
- Added JSON-backed store with `index.json`, `mails/*.json`, and `traces/*.jsonl`.
- Added index-first storage directory.
- Added neutral CLI commands: `write`, `index`, `read`, `trace`, `status`, `promote`, and `curate`.
- Kept legacy command aliases for existing users.
- Added tests proving index reads do not open memory bodies or raw traces.
