from neurodb.html_extractor import extract_html


def test_extracts_article_text_no_pages():
    html = (
        "<html><head><title>Memory Traces in the Cortex</title></head><body>"
        "<article>"
        "<h1>Memory Traces in the Cortex</h1>"
        "<h2>Abstract</h2>"
        "<p>" + ("The cortex encodes memory traces through synaptic plasticity mechanisms. " * 5) + "</p>"
        "<h2>Introduction</h2>"
        "<p>" + ("Long-term potentiation underpins spatial memory formation in hippocampal circuits. " * 5) + "</p>"
        "<h2>Results</h2>"
        "<p>" + ("The cortex encodes memory traces. " * 20) + "</p>"
        "<h2>Discussion</h2>"
        "<p>" + ("These findings suggest that neural plasticity drives memory consolidation. " * 5) + "</p>"
        "<h2>Conclusion</h2>"
        "<p>" + ("In summary, memory trace encoding relies on synaptic weight changes across cortical layers. " * 5) + "</p>"
        "</article>"
        "</body></html>"
    )
    art = extract_html(html)
    assert art.text_source == "html_extracted"
    assert art.sections[0].page is None
    assert "memory" in "\n".join(s.text for s in art.sections).lower()


def test_too_little_text_low_confidence():
    art = extract_html("<html><body><p>hi</p></body></html>")
    assert art.parse_confidence < 0.4
