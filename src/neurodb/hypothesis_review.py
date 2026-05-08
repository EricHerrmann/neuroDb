"""Research epoch — premium-model critique for draft hypotheses."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.model_telemetry import record_model_call
from neurodb.research_tools import create_hypothesis_review
from neurodb.schema import ResearchHypothesis


NEURODB_PREMIUM_MODEL = os.environ.get("NEURODB_PREMIUM_MODEL", "claude-opus-4-7")

_SYSTEM_PROMPT = """You are reviewing a draft neuroscience research hypothesis.
Treat the draft as unconfirmed. Do not present it as a finding.
Critique evidentiary support, unsupported claims, missing confounds, and revisions needed.
Return only valid JSON with keys: critique_text, unsupported_claims, missing_confounds, suggested_revisions.
unsupported_claims and missing_confounds must be arrays."""


def run_hypothesis_review(
    hypothesis_id: int,
    engine: Engine,
    client,
    model: str | None = None,
) -> dict:
    """Run a bounded premium-model critique and persist the linked review."""
    selected_model = model or NEURODB_PREMIUM_MODEL
    bundle = _load_hypothesis_bundle(engine, hypothesis_id)
    if bundle is None:
        return {"error": f"hypothesis {hypothesis_id} not found"}

    started = time.monotonic()
    response = client.messages.create(
        model=selected_model,
        max_tokens=1200,
        system=_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": _build_review_prompt(bundle),
        }],
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    record_model_call(
        engine,
        task_type="review.hypothesis",
        provider="anthropic",
        model=selected_model,
        mode="neuro_research",
        response=response,
        iteration=1,
        elapsed_ms=elapsed_ms,
    )

    parsed = _parse_review_response(_response_text(response))
    return create_hypothesis_review(
        engine,
        hypothesis_id,
        model=selected_model,
        critique_text=parsed["critique_text"],
        unsupported_claims=parsed["unsupported_claims"],
        missing_confounds=parsed["missing_confounds"],
        suggested_revisions=parsed["suggested_revisions"],
    )


def _load_hypothesis_bundle(engine: Engine, hypothesis_id: int) -> dict[str, Any] | None:
    with get_session(engine) as session:
        row = session.get(ResearchHypothesis, hypothesis_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "title": row.title,
            "mechanism": row.mechanism,
            "evidence": _json_list(row.evidence_json),
            "predictions": _json_list(row.predictions_json),
            "datasets": _json_list(row.datasets_json),
            "confounds": _json_list(row.confounds_json),
            "limitations": row.limitations,
            "status": row.status,
        }


def _build_review_prompt(bundle: dict[str, Any]) -> str:
    return json.dumps({
        "instruction": (
            "Review this draft hypothesis. Identify unsupported claims, missing "
            "confounds, and concrete revisions. This is a critique, not a finding."
        ),
        "draft_hypothesis": bundle,
    }, indent=2)


def _parse_review_response(text: str) -> dict:
    cleaned = _strip_code_fence(text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "critique_text": text.strip() or "Review response was empty.",
            "unsupported_claims": [],
            "missing_confounds": [],
            "suggested_revisions": "Revise manually; response was not structured JSON.",
        }

    return {
        "critique_text": str(data.get("critique_text") or "").strip() or "No critique provided.",
        "unsupported_claims": _coerce_list(data.get("unsupported_claims")),
        "missing_confounds": _coerce_list(data.get("missing_confounds")),
        "suggested_revisions": str(data.get("suggested_revisions") or "").strip()
        or "No revisions provided.",
    }


def _response_text(response) -> str:
    chunks: list[str] = []
    for block in _get_value(response, "content") or []:
        if _get_value(block, "type") == "text":
            text = _get_value(block, "text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _json_list(value: str) -> list:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return decoded if isinstance(decoded, list) else []


def _coerce_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _strip_code_fence(value: str) -> str:
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return value


def _get_value(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
