# MemoBox Dogfood Evaluation

This directory measures the outcome MemoBox is meant to improve: a fresh agent
finds trustworthy project evidence faster and avoids repeating investigations.
It does not evaluate semantic ranking; MemoBox remains a file protocol and the
model still decides which records to open.

## Groups

- **A — repository baseline:** the agent receives the checkout and Git history.
- **B — host-memory baseline:** the agent also has the host's built-in Memories.
- **C — MemoBox:** the agent also follows the project `.memobox` index/body/trace
  protocol. Record every MemoBox id actually used.

Use a fresh task/session for every run, keep the model and tool permissions the
same, and do not expose one group's notes to another group. Run all three groups
for every task in `tasks.json`.

## Record a run

Write one JSON object per line following `run.schema.json`. Times are wall-clock
seconds. `investigation_commands` counts repository/history/file-discovery tool
calls made before the first correct evidence is found. `context_units` can be
tokens when the host reports them or a consistent character estimate otherwise;
record the unit in `context_unit`.

```json
{"run_id":"2026-07-10-boundary-C","task_id":"file-protocol-boundary","group":"C","correctness":1.0,"evidence_seconds":34,"investigation_commands":3,"context_units":1800,"context_unit":"tokens","stale_memory_misuses":0,"maintenance_seconds":5,"used_memory_ids":["example-memory-id"],"notes":"Opened one mail body; trace was unnecessary."}
```

## Summarize

```bash
python3 evals/summarize.py evals/example-results.jsonl
python3 evals/summarize.py path/to/real-results.jsonl --json
```

The first dogfood milestone passes when C, compared with the strongest A/B
baseline:

- reduces median time to first correct evidence by at least 25%;
- reduces median investigation commands by at least 30%;
- does not reduce mean correctness;
- has zero stale-memory misuse; and
- spends less than 20% of saved evidence time maintaining MemoBox.

The example data only smoke-tests the reporting pipeline. Product decisions must
use fresh, real runs. Keep private `.memobox` data local; publish only explicitly
approved, redacted fixtures.
