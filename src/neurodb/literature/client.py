"""Orchestrates concurrent fan-out across active literature providers."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.literature import registry
from neurodb.literature.merge import dedup_and_merge
from neurodb.schema import LiteratureSearch

_LEGACY_COUNT_COLUMNS = {
    "pubmed": "pubmed_count",
    "semantic_scholar": "semantic_scholar_count",
    "arxiv": "arxiv_count",
}


class LiteratureSearchClient:
    """Search all active providers concurrently and return a merged envelope."""

    def __init__(self, engine: Engine, http_client: Any | None = None, timeout: float = 10.0) -> None:
        self._engine = engine
        self._http = http_client or httpx.Client(timeout=timeout, follow_redirects=True)
        self._timeout = timeout

    def search(self, query: str, limit: int = 10) -> dict:
        providers = registry.build_active_providers(self._http, timeout=self._timeout)
        per_provider: dict[str, tuple[list[dict], str | None]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(providers))) as executor:
            futures = {executor.submit(p.search, query, limit): p for p in providers}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    per_provider[provider.name] = future.result(timeout=self._timeout + 1)
                except Exception as exc:
                    per_provider[provider.name] = ([], f"{type(exc).__name__}: {exc}")

        all_results: list[dict] = []
        for results, _error in per_provider.values():
            all_results.extend(results)
        merged = dedup_and_merge(all_results, limit)

        counts = {name: len(results) for name, (results, _e) in per_provider.items()}
        self._log_search(query, counts, merged)

        return {
            "query": query,
            "result_count": len(merged),
            "results": merged,
            "providers": {
                name: _provider_status(results, error)
                for name, (results, error) in per_provider.items()
            },
        }

    def _log_search(self, query: str, counts: dict[str, int], results: list[dict]) -> None:
        legacy = {col: counts.get(name, 0) for name, col in _LEGACY_COUNT_COLUMNS.items()}
        with get_session(self._engine) as session:
            session.add(
                LiteratureSearch(
                    query=query,
                    results_json=json.dumps(results),
                    provider_counts_json=json.dumps(counts),
                    searched_at=datetime.now(timezone.utc).isoformat(),
                    **legacy,
                )
            )


def _provider_status(results: list[dict], error: str | None) -> dict:
    if error is not None:
        return {"status": "error", "count": 0, "error": error}
    return {"status": "ok", "count": len(results), "error": None}
