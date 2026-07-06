from __future__ import annotations

import tempfile
from pathlib import Path

from memobox import JsonMemoBoxStore, MemoryMail, MemoBoxSearcher


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonMemoBoxStore(Path(tmp) / ".memobox")

        for index in range(10):
            store.add_mail(
                MemoryMail(
                    id=f"task-{index}",
                    subject=f"Task {index}: MemoBox retrieval example",
                    summary="Index-first task memory for AI agents.",
                    project="memobox",
                    team="platform",
                    role="main-agent",
                    tags=["agent-memory", "index-first", f"task-{index}"],
                    context=f"Expandable body for task {index}.",
                    decisions=["Keep search index-first."],
                ),
                raw_trace=[{"event": "completed", "task": index}],
            )

        results = MemoBoxSearcher(store).search("index-first agent memory", project="memobox")
        print(f"matched: {len(results)}")
        print(f"top id: {results[0].entry.id}")
        print(f"top subject: {results[0].entry.subject}")

        mail = store.open_mail(results[0].entry.id)
        print(f"opened body: {mail.context}")
        print(f"raw trace events: {len(store.open_raw_trace(mail.id))}")


if __name__ == "__main__":
    main()

