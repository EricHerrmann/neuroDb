"""Build the active literature-provider list from environment config."""
from __future__ import annotations

import os

from neurodb.literature.providers.base import BaseLiteratureProvider
from neurodb.literature.providers.arxiv import ArxivProvider
from neurodb.literature.providers.biorxiv import BiorxivProvider
from neurodb.literature.providers.crossref import CrossrefProvider
from neurodb.literature.providers.europepmc import EuropePmcProvider
from neurodb.literature.providers.openalex import OpenAlexProvider
from neurodb.literature.providers.pubmed import PubmedProvider
from neurodb.literature.providers.semantic_scholar import SemanticScholarProvider

ALL_PROVIDER_CLASSES: list[type[BaseLiteratureProvider]] = [
    PubmedProvider,
    SemanticScholarProvider,
    ArxivProvider,
    OpenAlexProvider,
    EuropePmcProvider,
    CrossrefProvider,
    BiorxivProvider,
]


def _contact_email() -> str | None:
    return os.environ.get("NEURODB_CONTACT_EMAIL") or os.environ.get("UNPAYWALL_EMAIL")


def _disabled_names() -> set[str]:
    raw = os.environ.get("LITERATURE_PROVIDERS_DISABLED", "")
    return {name.strip() for name in raw.split(",") if name.strip()}


def build_active_providers(http, *, timeout: float = 10.0) -> list[BaseLiteratureProvider]:
    disabled = _disabled_names()
    email = _contact_email()
    providers: list[BaseLiteratureProvider] = []
    for cls in ALL_PROVIDER_CLASSES:
        if cls.name in disabled:
            continue
        providers.append(cls(http, timeout=timeout, contact_email=email))
    return providers
