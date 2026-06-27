from neurodb.literature import registry


class _Http:
    def get(self, *a, **k):
        raise AssertionError("not called")


def test_builds_all_providers_by_default(monkeypatch):
    monkeypatch.delenv("LITERATURE_PROVIDERS_DISABLED", raising=False)
    providers = registry.build_active_providers(_Http())
    names = {p.name for p in providers}
    assert {"pubmed", "semantic_scholar", "arxiv"} <= names


def test_disabled_providers_excluded(monkeypatch):
    monkeypatch.setenv("LITERATURE_PROVIDERS_DISABLED", "arxiv, pubmed")
    names = {p.name for p in registry.build_active_providers(_Http())}
    assert "arxiv" not in names
    assert "pubmed" not in names
    assert "semantic_scholar" in names


def test_contact_email_from_neurodb_var(monkeypatch):
    monkeypatch.setenv("NEURODB_CONTACT_EMAIL", "a@b.com")
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    assert registry._contact_email() == "a@b.com"


def test_contact_email_falls_back_to_unpaywall(monkeypatch):
    monkeypatch.delenv("NEURODB_CONTACT_EMAIL", raising=False)
    monkeypatch.setenv("UNPAYWALL_EMAIL", "u@p.com")
    assert registry._contact_email() == "u@p.com"
