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
      <PMID>123</PMID>
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


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <published>2024-01-15T10:00:00Z</published>
    <title>Predictive coding and synaptic plasticity</title>
    <summary>A preprint on plasticity mechanisms.</summary>
    <arxiv:doi>10.1000/arxivpublished</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.05678v2</id>
    <published>2024-02-20T10:00:00Z</published>
    <title>Cortical maps without a DOI</title>
    <summary>An unpublished preprint.</summary>
  </entry>
</feed>
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
    # PubMed result carries a landing-page URL built from its PMID.
    assert results[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"
    # Semantic Scholar result with no source URL falls back to the DOI resolver.
    assert results[1]["url"] == "https://doi.org/10.1000/review"
    # Semantic Scholar request must ask for the url field.
    s2_call = fake.calls[-1]
    assert "url" in s2_call[1]["params"]["fields"].split(",")

    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.query == "LTP"
        assert row.pubmed_count == 1
        assert row.semantic_scholar_count == 2
        assert len(json.loads(row.results_json)) == 2


def test_semantic_scholar_prefers_source_url_over_doi():
    engine = _engine()
    fake = _FakeHttp([
        _Response({"esearchresult": {"idlist": []}}),
        _Response({
            "data": [{
                "title": "Paper with a real landing page",
                "abstract": "Has both a url and a DOI.",
                "year": 2025,
                "citationCount": 7,
                "url": "https://www.semanticscholar.org/paper/abc123",
                "externalIds": {"DOI": "10.1000/haspage"},
                "publicationTypes": ["JournalArticle"],
            }]
        }),
    ])

    results = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    assert results[0]["url"] == "https://www.semanticscholar.org/paper/abc123"


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


def test_parse_arxiv_xml_normalizes_entries():
    from neurodb.literature_client import _parse_arxiv_xml

    results = _parse_arxiv_xml(ARXIV_XML)

    assert len(results) == 2
    first = results[0]
    assert first["title"] == "Predictive coding and synaptic plasticity"
    assert first["source"] == "arxiv"
    assert first["source_type"] == "preprint"
    assert first["year"] == 2024
    assert first["url"] == "https://arxiv.org/abs/2401.01234v1"
    assert first["doi"] == "10.1000/arxivpublished"
    assert first["citation_count"] is None
    # Preprint without a DOI: doi is None, url still built from id.
    assert results[1]["doi"] is None
    assert results[1]["url"] == "https://arxiv.org/abs/2402.05678v2"
