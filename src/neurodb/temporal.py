"""Temporal trust descriptor — spec invariant #8.

Vintage and training-cutoff relation are reasoned metadata, never a scalar
"newer is better" score. Currency status modifies the trust contract.
"""

# Model training cutoff is January 2026; year-level granularity is sufficient here.
CUTOFF_YEAR = 2026

_WARNING_STATUSES = ("superseded", "retracted", "contested")


def temporal_descriptor(year: int | None, currency_status: str = "current") -> dict:
    """Return vintage, cutoff relation, and any currency warning for a source."""
    if year is None:
        vintage = "unknown"
        cutoff_relation = "unknown"
    else:
        vintage = str(year)
        cutoff_relation = "post_cutoff" if year >= CUTOFF_YEAR else "pre_cutoff"

    warning = None
    if currency_status in _WARNING_STATUSES:
        warning = (
            f"This source is marked {currency_status}; surface this and do not "
            "present it as a clean citation."
        )

    return {
        "vintage": vintage,
        "cutoff_relation": cutoff_relation,
        "currency_status": currency_status,
        "warning": warning,
    }


def parse_year(raw) -> int | None:
    """Coerce a year value (LLM input or stored metadata) to int, or None."""
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def attach_temporal(results: list[dict]) -> list[dict]:
    """Attach a `temporal` descriptor to each knowledge-library search result.

    Mutates and returns the list so tutor and research retrieval share one
    disclosure path (spec invariants #6/#8).
    """
    for result in results:
        meta = result.get("metadata") or {}
        result["temporal"] = temporal_descriptor(
            parse_year(meta.get("year")), meta.get("currency_status", "current")
        )
    return results


# Shared disclosure rules appended to both the tutor and research system prompts.
TEMPORAL_DISCLOSURE_RULES = (
    "Source disclosure: when you use a Knowledge Library source, state its tier "
    "(full text, abstract, or metadata) and its vintage (year). If a source is "
    "post-training-cutoff (cutoff_relation = post_cutoff), say you have no training "
    "prior for it and are relying on the stored text. If a source carries a temporal "
    "warning (superseded, retracted, or contested), surface that warning instead of "
    "presenting it as a clean citation."
)
