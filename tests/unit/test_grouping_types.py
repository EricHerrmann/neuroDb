"""Unit tests for the grouping type registry and typed errors."""
import pytest

from neurodb.db.grouping_types import (
    GROUPING_TYPES,
    GroupingHierarchyError,
    UnknownGroupingType,
    require_known_type,
)


def test_registry_has_topic_and_concept():
    assert set(GROUPING_TYPES) >= {"topic", "concept"}
    assert GROUPING_TYPES["topic"].display == "Topic"
    assert GROUPING_TYPES["topic"].allow_agent_proposal is True
    assert GROUPING_TYPES["concept"].display == "Concept"


def test_require_known_type_accepts_registered():
    require_known_type("topic")
    require_known_type("concept")


def test_require_known_type_rejects_unknown():
    with pytest.raises(UnknownGroupingType):
        require_known_type("method")


def test_error_types_are_value_errors():
    assert issubclass(UnknownGroupingType, ValueError)
    assert issubclass(GroupingHierarchyError, ValueError)
