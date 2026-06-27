import json

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from neurodb import db as dbpkg
from neurodb.literature.client import LiteratureSearchClient
from neurodb.literature import registry
from neurodb.literature.providers.base import BaseLiteratureProvider
from neurodb.schema import LiteratureSearch


class _Stub(BaseLiteratureProvider):
    def __init__(self, name, rows):
        super().__init__(http=None)
        self.name = name
        self._rows = rows

    @property
    def endpoint(self):
        return "x"

    def build_params(self, q, n):
        return {}

    def parse_response(self, r):
        return []

    def normalize(self, raw):
        return raw

    def search(self, query, limit):
        return self._rows, None


def _rec(doi, source, cites):
    return {"title": "Shared", "doi": doi, "url": None, "abstract": "a",
            "source_type": "paper", "year": 2020, "citation_count": cites,
            "source": source, "sources": [source]}


def test_full_fanout_merges_and_is_idempotent(monkeypatch):
    eng = create_engine("duckdb:///:memory:")
    dbpkg.init_db(eng)
    providers = [
        _Stub("pubmed", [_rec("10.1/x", "pubmed", 1)]),
        _Stub("openalex", [_rec("10.1/x", "openalex", 8)]),
        _Stub("europepmc", [_rec("10.2/y", "europepmc", 4)]),
    ]
    monkeypatch.setattr(registry, "build_active_providers", lambda http, timeout=10.0: providers)
    client = LiteratureSearchClient(eng, http_client=object())

    env1 = client.search("synaptic plasticity", limit=10)
    assert env1["result_count"] == 2
    top = env1["results"][0]
    assert top["doi"] == "10.1/x" and top["citation_count"] == 8

    # Re-run: same merged results; one audit row per call, no duplicated result records.
    env2 = client.search("synaptic plasticity", limit=10)
    assert env2["results"] == env1["results"]
    with Session(eng) as s:
        rows = s.execute(select(func.count()).select_from(LiteratureSearch)).scalar_one()
        last = s.execute(select(LiteratureSearch).order_by(LiteratureSearch.id.desc())).scalars().first()
    assert rows == 2  # two searches logged
    counts = json.loads(last.provider_counts_json)
    assert counts == {"pubmed": 1, "openalex": 1, "europepmc": 1}
