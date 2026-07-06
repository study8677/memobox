from __future__ import annotations

import re
from collections import Counter

from memobox.models import IndexEntry, MemoryStatus, SearchResult
from memobox.store import JsonMemoBoxStore

DEFAULT_ACTIVE_STATUSES: tuple[MemoryStatus, ...] = ("inbox", "pinned", "needs_review")
STATUS_BOOST = {
    "pinned": 2.0,
    "needs_review": 0.25,
    "inbox": 0.0,
    "stale": -0.25,
    "archived": -0.5,
}
IMPORTANCE_BOOST = {
    "critical": 2.0,
    "high": 1.0,
    "normal": 0.0,
    "low": -0.25,
}


class MemoBoxSearcher:
    """Index-first retrieval. This class never opens mail bodies or raw traces."""

    def __init__(self, store: JsonMemoBoxStore):
        self.store = store

    def search(
        self,
        query: str,
        *,
        project: str | None = None,
        workspace: str | None = None,
        team: str | None = None,
        role: str | None = None,
        statuses: tuple[MemoryStatus, ...] | None = DEFAULT_ACTIVE_STATUSES,
        limit: int = 5,
    ) -> list[SearchResult]:
        query_terms = tokenize(query)
        results: list[SearchResult] = []

        for entry in self.store.list_index():
            if statuses is not None and entry.status not in statuses:
                continue
            if project and entry.project != project:
                continue
            if workspace and entry.workspace != workspace:
                continue
            if team and entry.team != team:
                continue
            if role and entry.role != role:
                continue

            score, matched_terms = score_entry(entry, query_terms)
            if score <= 0:
                continue
            results.append(SearchResult(entry=entry, score=score, matched_terms=matched_terms))

        results.sort(key=lambda item: (item.score, item.entry.updated_at), reverse=True)
        return results[:limit]


def score_entry(entry: IndexEntry, query_terms: list[str]) -> tuple[float, list[str]]:
    searchable = " ".join(
        [
            entry.subject,
            entry.summary,
            entry.project,
            entry.workspace,
            entry.team,
            entry.role,
            " ".join(entry.tags),
            " ".join(entry.participants),
        ]
    )
    haystack = Counter(tokenize(searchable))
    matched_terms: list[str] = []
    score = 0.0
    for term in query_terms:
        if term in haystack:
            matched_terms.append(term)
            score += 1.0 + min(haystack[term], 3) * 0.25
    if not matched_terms and query_terms:
        return 0.0, []

    score += STATUS_BOOST.get(entry.status, 0.0)
    score += IMPORTANCE_BOOST.get(entry.importance, 0.0)
    score += max(0.0, min(entry.confidence, 1.0)) * 0.5
    return score, sorted(set(matched_terms))


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_\-/.:]+|[\u4e00-\u9fff]+", text.lower())
