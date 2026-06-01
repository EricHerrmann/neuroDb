"""Type registry and typed errors for the unified groupings engine.

Valid grouping types live here, not in the DB. Adding a type is one line and
costs zero schema. Per-type policy travels on the spec.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupingTypeSpec:
    display: str
    allow_agent_proposal: bool


GROUPING_TYPES: dict[str, GroupingTypeSpec] = {
    "topic": GroupingTypeSpec(display="Topic", allow_agent_proposal=True),
    "concept": GroupingTypeSpec(display="Concept", allow_agent_proposal=True),
    # future: "method", "brain_region", "disease", "question_type"
}


class UnknownGroupingType(ValueError):
    """Raised when a grouping type is not in GROUPING_TYPES."""


class GroupingHierarchyError(ValueError):
    """Raised when re-parenting would violate the single-level invariant."""


def require_known_type(gtype: str) -> None:
    if gtype not in GROUPING_TYPES:
        raise UnknownGroupingType(f"Unknown grouping type: {gtype!r}")
