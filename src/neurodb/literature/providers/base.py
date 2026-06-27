"""Base class for live literature-search providers (template-method pattern).

Subclasses implement four hooks (endpoint, build_params, parse_response,
normalize). All HTTP, error capture, timeout, polite-pool, and normalization
helpers live here so adding a provider never duplicates plumbing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLiteratureProvider(ABC):
    name: str = "base"
    uses_polite_pool: bool = False

    def __init__(
        self,
        http: Any,
        *,
        timeout: float = 10.0,
        contact_email: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._http = http
        self._timeout = timeout
        self._contact_email = contact_email
        self._api_key = api_key

    # ---- concrete template method (do not override) ----
    def search(self, query: str, limit: int) -> tuple[list[dict], str | None]:
        try:
            response = self._fetch(query, limit)
            raw_rows = self.parse_response(response)
            return [self.normalize(row) for row in raw_rows], None
        except Exception as exc:  # providers must never raise
            return [], self._error_message(exc)

    # ---- concrete shared helpers ----
    def _fetch(self, query: str, limit: int):
        params = self._with_polite_pool(self.build_params(query, limit))
        response = self._http.get(
            self.endpoint,
            params=params,
            headers=self._request_headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response

    def _headers(self) -> dict:
        return {}

    def _request_headers(self) -> dict:
        """Provider-specific headers plus a polite User-Agent identifying this client.

        The contact email is sent in the User-Agent as a `mailto:` for services
        (e.g. Europe PMC) that have no email query parameter but use the agent
        string to identify and contact heavy users.
        """
        headers = {"User-Agent": self._user_agent()}
        headers.update(self._headers())
        return headers

    def _user_agent(self) -> str:
        if self._contact_email:
            return f"NeuroDb/1.0 (mailto:{self._contact_email})"
        return "NeuroDb/1.0"

    def _with_polite_pool(self, params: dict) -> dict:
        if self.uses_polite_pool and self._contact_email:
            params = {**params, "mailto": self._contact_email}
        return params

    @staticmethod
    def _truncate(text: str, limit: int = 300) -> str | None:
        value = " ".join((text or "").split())
        if not value:
            return None
        if len(value) <= limit:
            return value
        return f"{value[: limit - 3]}..."

    @staticmethod
    def _doi_url(doi: str | None) -> str | None:
        doi = (doi or "").strip()
        return f"https://doi.org/{doi}" if doi else None

    @staticmethod
    def _error_message(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _classify_source_type(pub_types: list[str], default: str) -> str:
        lowered = [str(value).lower() for value in pub_types or []]
        if any("review" in value for value in lowered):
            return "review"
        return default

    # ---- abstract hooks ----
    @property
    @abstractmethod
    def endpoint(self) -> str: ...

    @abstractmethod
    def build_params(self, query: str, limit: int) -> dict: ...

    @abstractmethod
    def parse_response(self, response) -> list[dict]: ...

    @abstractmethod
    def normalize(self, raw: dict) -> dict: ...
