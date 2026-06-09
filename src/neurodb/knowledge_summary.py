"""Shared knowledge-library summary construction (abstract-grounded).

Both the API approval route and the Streamlit approval page build the
learning-summary prompt here so the abstract-grounding (spec Phase 1) stays
consistent across every approval entry point.
"""
from neurodb.schema import Paper


def summary_prompt(row: Paper) -> str:
    """Build the model prompt for an approved source, grounded in its abstract."""
    lines = [
        "Create a concise structured neuroscience learning summary for this source.",
        f"Title: {row.title}",
        f"Source type: {row.source_type}",
        f"DOI: {row.doi or 'unknown'}",
        f"URL: {row.url or 'unknown'}",
        f"Topic context: {row.topic_context}",
    ]
    if row.abstract:
        lines.append("")
        lines.append("Summarize PRIMARILY from this abstract, not the title:")
        lines.append(f"Abstract: {row.abstract}")
    lines.append("")
    lines.append("Use sections: Key concepts, Relevance to neuroscience, Open questions.")
    return "\n".join(lines)


def fallback_summary(row: Paper) -> str:
    """Static summary used when no model provider is available."""
    if row.abstract:
        key = f"Key concepts (from abstract): {row.abstract}"
    else:
        key = (
            f"Key concepts: {row.title} was queued as a {row.source_type} while "
            f"discussing {row.topic_context}."
        )
    return (
        f"{key}\n\n"
        "Relevance to neuroscience: This source was approved for future Neuro-Tutor retrieval.\n\n"
        "Open questions: Add a richer model-generated summary when provider access is available."
    )
