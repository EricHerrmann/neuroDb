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
