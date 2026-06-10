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


def test_build_ledger_handles_block_list_content():
    # Mirrors the real provider format_tool_result shape: content is a list of blocks.
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "verify_quote",
             "input": {"text": "hippocampus consolidates"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": [{"type": "text", "text": '{"matched": true, "chunk_id": "c1"}'}]}]},
    ]
    ledger = build_quote_ledger(messages)
    assert ledger == [LedgerEntry(quoted_text="hippocampus consolidates", matched=True)]


def test_build_ledger_uses_actual_format_tool_result():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient
    import json as _json
    # Verify format_tool_result produces the list-of-blocks shape without needing network/config.
    # AnthropicModelClient.__init__ only stores self._client; we can call the pure formatter
    # via a bare instance if we bypass __init__.
    client_instance = AnthropicModelClient.__new__(AnthropicModelClient)
    fmt = client_instance.format_tool_result("t1", _json.dumps({"matched": True}))
    # fmt must be {"type":"tool_result","tool_use_id":"t1","content":[{"type":"text","text":"..."}]}
    assert fmt["type"] == "tool_result"
    assert isinstance(fmt["content"], list), "format_tool_result must return list-shaped content"
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "verify_quote",
             "input": {"text": "x"}}]},
        {"role": "user", "content": [fmt]},
    ]
    assert build_quote_ledger(messages)[0].matched is True
