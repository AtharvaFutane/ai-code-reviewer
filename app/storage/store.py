# app/storage/store.py
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from app.api.models import ReviewReport, ReviewSummary


class ReviewStore:
    """
    Thread-safe in-memory store for ReviewReport objects.
    
    Architectural Decision: Using asyncio.Lock (not threading.Lock) because
    FastAPI runs in an async event loop. All reads/writes are awaited.
    Reviews persist only for the session lifetime — as specified.
    """

    def __init__(self) -> None:
        self._store: Dict[str, ReviewReport] = {}
        self._meta: Dict[str, str] = {}  # review_id → language
        self._lock = asyncio.Lock()

    async def save(self, report: ReviewReport, language: str) -> None:
        async with self._lock:
            self._store[report.review_id] = report
            self._meta[report.review_id] = language

    async def get(self, review_id: str) -> Optional[ReviewReport]:
        async with self._lock:
            return self._store.get(review_id)

    async def list_all(self) -> List[ReviewSummary]:
        async with self._lock:
            return [
                ReviewSummary(
                    review_id=r.review_id,
                    pr_summary=r.pr_summary,
                    verdict=r.verdict,
                    overall_severity=r.overall_severity,
                    language=self._meta.get(r.review_id, "unknown"),
                    created_at=r.created_at,
                )
                for r in sorted(
                    self._store.values(),
                    key=lambda x: x.created_at,
                    reverse=True,
                )
            ]

    async def count(self) -> int:
        async with self._lock:
            return len(self._store)


# Module-level singleton — imported by routes and used throughout
review_store = ReviewStore()
