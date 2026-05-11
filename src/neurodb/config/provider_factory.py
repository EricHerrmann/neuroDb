"""Build configured model provider clients from available API keys."""
from __future__ import annotations

import os

from neurodb.config.model_client import ModelClient
from neurodb.config.providers.anthropic_client import AnthropicModelClient
from neurodb.config.providers.openai_client import OpenAIModelClient

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


def build_provider_clients() -> dict[str, ModelClient]:
    """Return provider-name to ModelClient mappings for configured API keys."""
    providers: dict[str, ModelClient] = {}

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        import anthropic

        providers["anthropic"] = AnthropicModelClient(
            anthropic.Anthropic(api_key=anthropic_key)
        )

    openai_key = os.environ.get("OPENAI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    # Google is the provider for Gemini models; the API key is issued by Google AI Studio.
    gemini_key = os.environ.get("GOOGLE_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if openai_key or groq_key or gemini_key or deepseek_key:
        try:
            import openai
        except ModuleNotFoundError:
            return providers

        if openai_key:
            providers["openai"] = OpenAIModelClient(
                openai.OpenAI(api_key=openai_key)
            )
        if groq_key:
            providers["groq"] = OpenAIModelClient(
                openai.OpenAI(api_key=groq_key, base_url=_GROQ_BASE_URL)
            )
        if gemini_key:
            providers["gemini"] = OpenAIModelClient(
                openai.OpenAI(api_key=gemini_key, base_url=_GEMINI_BASE_URL)
            )
        if deepseek_key:
            providers["deepseek"] = OpenAIModelClient(
                openai.OpenAI(api_key=deepseek_key, base_url=_DEEPSEEK_BASE_URL)
            )

    return providers
