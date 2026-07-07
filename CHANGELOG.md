# Changelog

## 0.1.0

- Initial MemoBox package.
- Added model-readable memory mail model.
- Added JSON-backed store with `index.json`, `mails/*.json`, and `traces/*.jsonl`.
- Added index-first storage directory.
- Added neutral CLI commands: `write`, `index`, `read`, `trace`, `status`, `promote`, and `curate`.
- Kept legacy command aliases for existing users.
- Added tests proving index reads do not open memory bodies or raw traces.
