from neurodb.literature.merge import dedup_and_merge


def _rec(**kw):
    base = {"title": "T", "doi": None, "url": None, "abstract": None,
            "source_type": "paper", "year": None, "citation_count": None,
            "source": "x", "sources": ["x"]}
    base.update(kw)
    return base


def test_dedup_by_doi_merges_metadata():
    a = _rec(doi="10.1/x", abstract="short", citation_count=3, source="pubmed", sources=["pubmed"])
    b = _rec(doi="10.1/X", abstract="a much longer abstract", citation_count=10,
             source="openalex", sources=["openalex"], source_type="review")
    out = dedup_and_merge([a, b], limit=10)
    assert len(out) == 1
    assert out[0]["abstract"] == "a much longer abstract"
    assert out[0]["citation_count"] == 10
    assert out[0]["source_type"] == "review"
    assert out[0]["sources"] == ["openalex", "pubmed"]


def test_dedup_title_year_fallback_when_no_doi():
    a = _rec(title="Hippocampal LTP!", year=2020, source="arxiv", sources=["arxiv"])
    b = _rec(title="hippocampal  ltp", year=2020, source="europepmc", sources=["europepmc"])
    out = dedup_and_merge([a, b], limit=10)
    assert len(out) == 1
    assert set(out[0]["sources"]) == {"arxiv", "europepmc"}


def test_distinct_records_kept():
    a = _rec(doi="10.1/a")
    b = _rec(doi="10.1/b")
    out = dedup_and_merge([a, b], limit=10)
    assert len(out) == 2


def test_ranking_citations_desc_then_year_desc():
    a = _rec(doi="10.1/a", citation_count=5, year=2019)
    b = _rec(doi="10.1/b", citation_count=50, year=2018)
    c = _rec(doi="10.1/c", citation_count=None, year=2024)
    out = dedup_and_merge([a, b, c], limit=10)
    assert [r["doi"] for r in out] == ["10.1/b", "10.1/a", "10.1/c"]


def test_trims_to_limit_after_merge():
    recs = [_rec(doi=f"10.1/{i}", citation_count=i) for i in range(5)]
    out = dedup_and_merge(recs, limit=2)
    assert len(out) == 2
    assert out[0]["doi"] == "10.1/4"
