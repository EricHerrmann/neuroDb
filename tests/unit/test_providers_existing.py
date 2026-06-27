from neurodb.literature.providers.pubmed import PubmedProvider
from neurodb.literature.providers.semantic_scholar import SemanticScholarProvider
from neurodb.literature.providers.arxiv import ArxivProvider

PUBMED_SEARCH = {"esearchresult": {"idlist": ["123"]}}
PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<ArticleTitle>LTP and memory</ArticleTitle>
<Abstract><AbstractText>LTP is plasticity.</AbstractText></Abstract>
<Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
<PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList>
<ELocationID EIdType="doi">10.1000/ltp</ELocationID>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""

S2_JSON = {"data": [{"title": "S2 paper", "abstract": "abc", "year": 2022,
                     "citationCount": 9, "externalIds": {"DOI": "10.5/s2"},
                     "publicationTypes": ["JournalArticle"], "url": "https://s2/abc"}]}

ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2401.01234v1</id><published>2024-01-15T10:00:00Z</published>
<title>Predictive coding</title><summary>preprint</summary>
<arxiv:doi>10.1/arx</arxiv:doi></entry></feed>"""


class _Resp:
    def __init__(self, json_data=None, text=""):
        self._json = json_data
        self.text = text
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _RouteHttp:
    """Routes by URL substring to a queued response."""
    def __init__(self, routes):
        self.routes = routes

    def get(self, url, params=None, headers=None, timeout=None):
        for needle, resp in self.routes.items():
            if needle in url:
                return resp
        raise AssertionError(f"no route for {url}")


def test_pubmed_normalizes_with_review_type():
    http = _RouteHttp({"esearch": _Resp(json_data=PUBMED_SEARCH),
                       "efetch": _Resp(text=PUBMED_XML)})
    results, error = PubmedProvider(http).search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["title"] == "LTP and memory"
    assert r["doi"] == "10.1000/ltp"
    assert r["source"] == "pubmed"
    assert r["source_type"] == "review"
    assert r["year"] == 2024
    assert r["sources"] == ["pubmed"]


def test_pubmed_empty_idlist_returns_no_rows():
    http = _RouteHttp({"esearch": _Resp(json_data={"esearchresult": {"idlist": []}})})
    results, error = PubmedProvider(http).search("ltp", 5)
    assert results == []
    assert error is None


def test_semantic_scholar_normalizes():
    http = _RouteHttp({"semanticscholar": _Resp(json_data=S2_JSON)})
    results, error = SemanticScholarProvider(http).search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["doi"] == "10.5/s2"
    assert r["citation_count"] == 9
    assert r["source"] == "semantic_scholar"


def test_arxiv_normalizes_preprint():
    http = _RouteHttp({"arxiv": _Resp(text=ARXIV_XML)})
    results, error = ArxivProvider(http).search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["source_type"] == "preprint"
    assert r["doi"] == "10.1/arx"
    assert r["url"] == "https://arxiv.org/abs/2401.01234v1"
