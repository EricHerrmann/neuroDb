"""Unit tests for the shared abstract-grounded summary helpers."""
from neurodb.knowledge_summary import fallback_summary, summary_prompt
from neurodb.schema import Paper


def _paper(**kw):
    base = dict(
        title="CREB and engram allocation", normalized_title="creb",
        source_type="paper", topic_context="memory", status="approved",
        queued_at="now",
    )
    base.update(kw)
    return Paper(**base)


def test_summary_prompt_includes_abstract():
    out = summary_prompt(_paper(abstract="CREB biases engram allocation."))
    assert "Abstract: CREB biases engram allocation." in out
    assert "Summarize PRIMARILY" in out


def test_summary_prompt_without_abstract():
    out = summary_prompt(_paper(abstract=None))
    assert "Abstract:" not in out
    assert "Summarize PRIMARILY" not in out


def test_fallback_summary_prefers_abstract():
    assert "from abstract" in fallback_summary(_paper(abstract="X finding.")).lower()
    assert "from abstract" not in fallback_summary(_paper(abstract=None)).lower()
