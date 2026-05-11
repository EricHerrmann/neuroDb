import sys
from types import SimpleNamespace

from neurodb.config.provider_factory import build_provider_clients
from neurodb.config.providers.anthropic_client import AnthropicModelClient
from neurodb.config.providers.openai_client import OpenAIModelClient


class _AnthropicSDK:
    def __init__(self, api_key):
        self.api_key = api_key


class _OpenAISDK:
    def __init__(self, api_key, base_url=None):
        self.api_key = api_key
        self.base_url = base_url


def test_build_provider_clients_registers_available_api_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        SimpleNamespace(Anthropic=_AnthropicSDK),
    )
    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=_OpenAISDK),
    )

    providers = build_provider_clients()

    assert isinstance(providers["anthropic"], AnthropicModelClient)
    assert isinstance(providers["openai"], OpenAIModelClient)
    assert isinstance(providers["groq"], OpenAIModelClient)


def test_build_provider_clients_registers_gemini_when_key_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "gemini-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=_OpenAISDK),
    )

    providers = build_provider_clients()

    assert "gemini" in providers
    assert isinstance(providers["gemini"], OpenAIModelClient)


def test_build_provider_clients_gemini_uses_correct_base_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "gemini-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=_OpenAISDK),
    )

    providers = build_provider_clients()

    sdk = providers["gemini"]._client
    assert "generativelanguage.googleapis.com" in sdk.base_url


def test_build_provider_clients_skips_missing_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    providers = build_provider_clients()

    assert providers == {}
