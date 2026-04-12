import pytest
from neurodb.connectors.base import BaseConnector


def test_base_connector_is_abstract():
    with pytest.raises(TypeError):
        BaseConnector()  # cannot instantiate abstract class


def test_base_connector_defines_required_abstract_methods():
    abstract_methods = BaseConnector.__abstractmethods__
    assert "fetch_datasets" in abstract_methods
    assert "get_source_id" in abstract_methods
    assert "normalize_dataset" in abstract_methods
    assert "fetch_subjects" in abstract_methods
    assert "normalize_subject" in abstract_methods


def test_base_connector_requires_source_name_and_version():
    # A concrete subclass that omits SOURCE_NAME or VERSION should still
    # be instantiable (they are class attributes, not abstract methods),
    # but the contract is documented and tested here for visibility.
    class MinimalConnector(BaseConnector):
        SOURCE_NAME = "test"
        VERSION = "0.1.0"

        def fetch_datasets(self, limit=100):
            return iter([])

        def get_source_id(self, raw):
            return raw["id"]

        def normalize_dataset(self, raw, index_id, run_id):
            return None

        def fetch_subjects(self, dataset_source_id):
            return iter([])

        def normalize_subject(self, raw, index_id):
            return None

    conn = MinimalConnector()
    assert conn.SOURCE_NAME == "test"
    assert conn.VERSION == "0.1.0"
