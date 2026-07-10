# Changelog

## 0.1.0 - 2026-07-10

- Initial public alpha release.
- Added the JSON-backed `index.json`, `mails/*.json`, and `traces/*.jsonl` storage layers.
- Added status, promotion, merge, Python API, and skills-only plugin surfaces.
- Reframed MemoBox as an index-first local file protocol for AI agents.
- Removed CLI read wrappers and legacy aliases: `index`, `read`, `trace`, `add`, `inbox`, `map`, `show`, `raw`, `recall`, and `remember`.
- Kept the CLI focused on writes and maintenance: `init`, `write`, `status`, `promote`, `curate`, `verify`, and `rebuild-index`.
- Updated docs, skills, and plugin metadata to read `.memobox/index.json`, `mails/*.json`, and `traces/*.jsonl` directly with Bash.
- Made `mails/*.json` the durable truth source, with cross-process locking, atomic file replacement, integrity verification, and safe index rebuilds.
- Added an opt-in start/read/end/write agent loop with strict memory-worthiness and sensitive-data gates.
- Made PreCompact payload persistence opt-in and added a per-session disable switch for sensitive work.
- Added a repeatable A/B/C dogfood evaluation with local result summaries and acceptance thresholds.
