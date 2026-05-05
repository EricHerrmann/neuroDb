import json

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.literature_client import LiteratureSearchClient
from neurodb.schema import Base, LiteratureSearch


PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Hippocampal long-term potentiation and memory</ArticleTitle>
        <Abstract><AbstractText>Long-term potentiation is a model of synaptic plasticity.</AbstractText></Abstract>
        <Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
        <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
        <ELocationID EIdType="doi">10.1000/ltp</ELocationID>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class _Response:
    def __init__(self, json_data=None, text=""):
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class _FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_literature_search_schema_table_created():
    engine = _engine()
    assert "literature_searches" in Base.metadata.tables
    with Session(engine) as session:
        session.add(
            LiteratureSearch(
                query="plasticity",
                pubmed_count=1,
                semantic_scholar_count=0,
                results_json="[]",
                searched_at="2026-05-05T00:00:00",
            )
        )
        session.commit()
        assert session.query(LiteratureSearch).count() == 1


def test_search_parses_pubmed_and_semantic_scholar_and_dedups_by_doi():
    engine = _engine()
    fake = _FakeHttp([
        _Response({"esearchresult": {"idlist": ["123"]}}),
        _Response(text=PUBMED_XML),
        _Response({
            "data": [
                {
                    "title": "Duplicate Semantic Scholar LTP",
                    "abstract": "Same DOI should be deduplicated.",
                    "year": 2023,
                    "citationCount": 42,
                    "externalIds": {"DOI": "10.1000/ltp"},
                    "publicationTypes": ["JournalArticle"],
                },
                {
                    "title": "A review of cortical plasticity",
                    "abstract": "Review abstract.",
                    "year": 2022,
                    "citationCount": 12,
                    "externalIds": {"DOI": "10.1000/review"},
                    "publicationTypes": ["Review"],
                },
            ]
        }),
    ])

    results = LiteratureSearchClient(engine, http_client=fake).search("LTP")

    assert [row["doi"] for row in results] == ["10.1000/ltp", "10.1000/review"]
    assert results[0]["source"] == "pubmed"
    assert results[1]["source"] == "semantic_scholar"
    assert results[1]["source_type"] == "review"

    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.query == "LTP"
        assert row.pubmed_count == 1
        assert row.semantic_scholar_count == 2
        assert len(json.loads(row.results_json)) == 2


def test_search_gracefully_logs_when_one_source_times_out():
    engine = _engine()
    fake = _FakeHttp([
        httpx.TimeoutException("pubmed down"),
        _Response({
            "data": [{
                "title": "Semantic Scholar fallback",
                "abstract": "Fallback result.",
                "year": 2024,
                "citationCount": 3,
                "externalIds": {"DOI": "10.1000/fallback"},
                "publicationTypes": ["JournalArticle"],
            }]
        }),
    ])

    results = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    assert len(results) == 1
    assert results[0]["source"] == "semantic_scholar"
    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.pubmed_count == 0
        assert row.semantic_scholar_count == 1
