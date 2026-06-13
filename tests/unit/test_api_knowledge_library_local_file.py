import shutil
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from neurodb.api.routes.knowledge_library import _phase2b_parse
from neurodb.db import get_session
from neurodb.full_text_client import SuppliedInput
from neurodb.schema import Paper
from tests.unit.test_api_knowledge_library import _make_duckdb_client


def _paper():
    return type("P", (), {"url": None, "doi": None, "id": 1, "open_access_pdf": None})()


def test_phase2b_parse_reads_local_pdf():
    art = _phase2b_parse(_paper(), SuppliedInput(path="tests/fixtures/sample.pdf"))
    assert art is not None
    assert art.text_source == "pdf_pymupdf"
    assert art.fetched_url == "sample.pdf"
    assert art.sections[0].page == 1


def _approved_paper(engine, **kw):
    with get_session(engine) as s:
        p = Paper(title="P", normalized_title="p", source_type="paper", topic_context="x",
                  status="approved", queued_at="t", data_tier="abstract",
                  currency_status="current", **kw)
        s.add(p); s.flush(); return p.id


def test_library_files_lists_dropped_files(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4")
    client, _ = _make_duckdb_client()
    resp = client.get("/api/knowledge-library/library-files")
    assert resp.status_code == 200
    assert any(f["name"] == "paper.pdf" for f in resp.json())


def test_acquire_txt_source_path_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    (tmp_path / "note.md").write_text("# Title\n\nSome real body text about memory.\n")
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    resp = client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                       json={"source_path": "note.md"})
    assert resp.status_code == 200
    with Session(engine) as s:
        assert s.get(Paper, pid).full_text_status == "verified"


def test_acquire_pdf_source_path_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    shutil.copy("tests/fixtures/sample.pdf", tmp_path / "sample.pdf")
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                json={"source_path": "sample.pdf"})
    with Session(engine) as s:
        assert s.get(Paper, pid).full_text_status == "verified"


def test_acquire_traversal_path_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    resp = client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                       json={"source_path": "../../etc/passwd"})
    assert resp.status_code == 400


def test_acquire_missing_file_404(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    resp = client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                       json={"source_path": "ghost.pdf"})
    assert resp.status_code == 404
