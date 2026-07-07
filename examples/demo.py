from __future__ import annotations

import tempfile
from pathlib import Path

from memobox import JsonMemoBoxStore, MemoryMail


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonMemoBoxStore(Path(tmp) / ".memobox")

        for index in range(10):
            store.add_mail(
                MemoryMail(
                    id=f"task-{index}",
                    subject=f"Record {index}: MemoBox index example",
                    summary="Index-first model-readable memory storage.",
                    project="memobox",
                    team="platform",
                    role="model",
                    tags=["model-memory", "index-first", f"task-{index}"],
                    context=f"Expandable body for task {index}.",
                    decisions=["Keep index reads separate from body and trace reads."],
                ),
                raw_trace=[{"event": "completed", "task": index}],
            )

        directory = store.list_index()
        print(f"index entries: {len(directory)}")
        print(f"first id: {directory[0].id}")
        print(f"first subject: {directory[0].subject}")

        mail = store.open_mail(directory[0].id)
        print(f"opened body: {mail.context}")
        print(f"raw trace events: {len(store.open_raw_trace(mail.id))}")


if __name__ == "__main__":
    main()
