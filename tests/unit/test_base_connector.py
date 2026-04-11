import pytest
from neurodb.connectors.base import BaseConnector

def test_base_connector_is_abstract():
    with pytest.raises(TypeError):
        BaseConnector()  # cannot instantiate abstract class
