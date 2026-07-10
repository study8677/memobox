# MemoBox Dogfood Evaluation

This directory measures the outcome MemoBox is meant to improve: a fresh agent
finds trustworthy project evidence faster and avoids repeating investigations.
It does not evaluate semantic ranking; MemoBox remains a file protocol and the
model still decides which records to open.

## Groups

- **A — repository baseline:** the agent receives the checkout and Git history.
- **B — host-memory baseline:** the agent also has the host's built-in Memories.
- **C — MemoBox:** the agent also follows the project `.memobox` index/body/trace
  protocol. Separately record every body opened and every memory that materially
  changed the plan, decision, implementation, or verification.

Use a fresh task/session for every run, keep the model and tool permissions the
same, and do not expose one group's notes to another group. Run all three groups
for every task in `tasks.json`.

## Record a completed run

Use the zero-dependency recorder so every entry is checked against `tasks.json`,
the run id cannot duplicate an existing entry, and malformed metrics cannot be
appended. It records one completed run; it never generates runs or invents
measurements. Passing validation is not evidence that the task actually ran.

```bash
python3 evals/record.py work/dogfood-results.jsonl \
  --run-id 2026-07-10-boundary-C \
  --task-id file-protocol-boundary \
  --group C \
  --correctness 1 \
  --evidence-seconds 34 \
  --investigation-commands 3 \
  --context-units 1800 \
  --context-unit tokens \
  --stale-memory-misuses 0 \
  --maintenance-seconds 5 \
  --opened-memory-id first-memory-id \
  --opened-memory-id second-memory-id \
  --reused-memory-id first-memory-id \
  --notes "Second body was opened but did not affect the result."
```

Times are wall-clock seconds. `investigation_commands` counts repository,
history, and file-discovery tool calls made before the first correct evidence.
`context_units` can be tokens when the host reports them or one consistent
character estimate otherwise. A reused id must also appear in opened ids. Groups
A and B cannot record MemoBox ids, maintenance, or stale-memory misuse.

## Summarize

```bash
python3 evals/summarize.py evals/example-results.jsonl
python3 evals/summarize.py work/dogfood-results.jsonl --json
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
