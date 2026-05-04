from neurodb.connectors.allen_brain import AllenBrainConnector
from neurodb.connectors.dandi import DandiConnector
from neurodb.connectors.neurovault import NeuroVaultConnector
from neurodb.connectors.openneuro import OpenNeuroConnector

ALL_CONNECTORS = [
    AllenBrainConnector,
    DandiConnector,
    NeuroVaultConnector,
    OpenNeuroConnector,
]
