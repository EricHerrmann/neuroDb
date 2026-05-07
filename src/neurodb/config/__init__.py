"""Config Control epoch — model routing, provider abstraction, capability gating.

This package is the target home for all Config Control epoch modules.
Planned modules (not yet implemented):

  config/model_client.py      — ModelClient ABC and normalized response types
  config/task_router.py       — TaskRouter: task_type → (ModelClient, model_id, max_tokens)
  config/model_config.py      — reads neurodb_models.toml
  config/providers/
    anthropic_client.py       — AnthropicModelClient
    openai_client.py          — OpenAIModelClient (also covers Groq)

Existing flat-layout modules that migrate here when next significantly changed:
  prefs.py → config/prefs.py

Interface to Agent Core: TaskRouter.route(task_type) returns
(ModelClient, model_id, max_tokens) for injection at agent construction.
No agent reads env vars or config files internally.
"""
