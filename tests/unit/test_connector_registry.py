from neurodb.connectors import ALL_CONNECTORS
from neurodb.connectors.base import BaseConnector


def test_all_connectors_are_base_connector_subclasses():
    for connector_cls in ALL_CONNECTORS:
        assert issubclass(connector_cls, BaseConnector), (
            f"{connector_cls.__name__} is not a BaseConnector subclass"
        )


def test_all_connectors_have_source_name():
    for connector_cls in ALL_CONNECTORS:
        assert hasattr(connector_cls, "SOURCE_NAME"), (
            f"{connector_cls.__name__} missing SOURCE_NAME"
        )


def test_connector_source_names_are_unique():
    names = [c.SOURCE_NAME for c in ALL_CONNECTORS]
    assert len(names) == len(set(names)), "Duplicate SOURCE_NAME values in ALL_CONNECTORS"


def test_all_four_sources_registered():
    names = {c.SOURCE_NAME for c in ALL_CONNECTORS}
    assert names == {"openneuro", "dandi", "neurovault", "allen_brain"}
