from neurodb.chapter_registry import lookup_chapter, REGISTRY


def test_known_chapter_returns_title_and_topics():
    result = lookup_chapter("augustine_7e", 12)
    assert result is not None
    assert result["title"] == "Central Visual Pathways"
    assert "retinotopy" in result["topics"]


def test_unknown_chapter_returns_none():
    result = lookup_chapter("augustine_7e", 999)
    assert result is None


def test_unknown_book_returns_none():
    result = lookup_chapter("unknown_book", 1)
    assert result is None


def test_registry_has_augustine_7e():
    assert "augustine_7e" in REGISTRY
    assert REGISTRY["augustine_7e"]["display_name"] == "Neuroscience, 7th ed. — Augustine et al."


def test_chapter_11_known():
    result = lookup_chapter("augustine_7e", 11)
    assert result is not None
    assert result["title"] == "Vision: The Eye"
