from neurodb.quote_verify import (
    LedgerEntry,
    build_quote_ledger,
    normalize_quote,
    reconcile_quotes,
    verify_quote,
)


def test_normalize_collapses_whitespace_and_dashes():
    assert normalize_quote("the  hippo\ncampus—works") == "the hippocampus-works"


def test_verify_matches_substring_of_chunk():
    chunks = [{"chunk_id": "c1", "text": "The hippocampus consolidates memory.",
               "section": "Intro", "char_start": 0, "char_end": 36}]
    m = verify_quote("hippocampus consolidates", chunks)
    assert m is not None and m["chunk_id"] == "c1"


def test_verify_rejects_absent_text():
    chunks = [{"chunk_id": "c1", "text": "The hippocampus.", "section": None,
               "char_start": 0, "char_end": 16}]
    assert verify_quote("the cerebellum coordinates movement", chunks) is None


def test_build_ledger_from_messages():
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "verify_quote",
             "input": {"text": "hippocampus consolidates"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": '{"matched": true, "chunk_id": "c1"}'}]},
    ]
    ledger = build_quote_ledger(messages)
    assert ledger == [LedgerEntry(quoted_text="hippocampus consolidates", matched=True)]


def test_reconcile_flags_unverified_quote():
    ledger = [LedgerEntry("hippocampus consolidates", True)]
    answer = 'It says "hippocampus consolidates memory" and also "the cerebellum is unrelated here".'
    warnings = reconcile_quotes(answer, ledger, min_quote_chars=10)
    assert any("cerebellum is unrelated" in w for w in warnings)
    assert not any("hippocampus consolidates memory" in w for w in warnings)


def test_reconcile_flags_false_positive():
    ledger = [LedgerEntry("hippocampus consolidates", False)]
    answer = 'Quote: "hippocampus consolidates strongly here".'
    warnings = reconcile_quotes(answer, ledger, min_quote_chars=10)
    assert len(warnings) == 1
