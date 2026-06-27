from neurodb.literature.providers.openalex import OpenAlexProvider
from neurodb.literature.providers.europepmc import EuropePmcProvider
from neurodb.literature.providers.crossref import CrossrefProvider
from neurodb.literature.providers.biorxiv import BiorxivProvider

OPENALEX = {"results": [{
    "display_name": "OA paper", "doi": "https://doi.org/10.7/oa",
    "publication_year": 2023, "cited_by_count": 42, "type": "article",
    "abstract_inverted_index": {"Plasticity": [0], "matters": [1]},
    "id": "https://openalex.org/W1"}]}

EUROPEPMC = {"resultList": {"result": [{
    "title": "EPMC paper", "doi": "10.8/epmc", "pubYear": "2021",
    "citedByCount": 7, "abstractText": "epmc abstract",
    "pubType": "review", "fullTextUrlList": {}}]}}

CROSSREF = {"message": {"items": [{
    "title": ["Crossref paper"], "DOI": "10.9/cr",
    "published": {"date-parts": [[2019, 5]]},
    "is-referenced-by-count": 3, "abstract": "<p>cr abstract</p>",
    "type": "journal-article"}]}}

BIORXIV = {"resultList": {"result": [{
    "title": "Preprint paper", "doi": "10.10/pp", "pubYear": "2024",
    "citedByCount": 0, "abstractText": "pp abstract",
    "pubType": "preprint", "source": "PPR"}]}}


class _Resp:
    def __init__(self, json_data):
        self._json = json_data
        self.text = ""
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _Http:
    def __init__(self, resp):
        self.resp = resp
        self.last_params = None
        self.last_headers = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.last_params = params
        self.last_headers = headers
        return self.resp


def test_openalex_normalizes_and_uses_polite_pool():
    http = _Http(_Resp(OPENALEX))
    results, error = OpenAlexProvider(http, contact_email="me@x.com").search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["title"] == "OA paper"
    assert r["doi"] == "10.7/oa"
    assert r["citation_count"] == 42
    assert r["abstract"] == "Plasticity matters"
    assert r["source"] == "openalex"
    assert http.last_params.get("mailto") == "me@x.com"


def test_europepmc_normalizes_review():
    results, error = EuropePmcProvider(_Http(_Resp(EUROPEPMC))).search("ltp", 5)
    assert error is None
    assert results[0]["source_type"] == "review"
    assert results[0]["doi"] == "10.8/epmc"
    assert results[0]["citation_count"] == 7


def test_europepmc_carries_contact_email_in_user_agent():
    """Europe PMC has no email query param; the contact email rides in User-Agent."""
    http = _Http(_Resp(EUROPEPMC))
    EuropePmcProvider(http, contact_email="me@x.com").search("ltp", 5)
    ua = http.last_headers.get("User-Agent")
    assert ua and "mailto:me@x.com" in ua
    # And it is NOT smuggled in as an unsupported query param.
    assert "mailto" not in http.last_params
    assert "email" not in http.last_params


def test_crossref_strips_abstract_markup_and_year():
    http = _Http(_Resp(CROSSREF))
    results, error = CrossrefProvider(http, contact_email="me@x.com").search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["title"] == "Crossref paper"
    assert r["year"] == 2019
    assert "<p>" not in (r["abstract"] or "")
    assert http.last_params.get("mailto") == "me@x.com"


def test_biorxiv_marks_preprint():
    results, error = BiorxivProvider(_Http(_Resp(BIORXIV))).search("ltp", 5)
    assert error is None
    assert results[0]["source_type"] == "preprint"
    assert results[0]["source"] == "biorxiv"
