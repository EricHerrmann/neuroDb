from abc import ABC, abstractmethod
from typing import Any, Iterator
from neurodb.schema import Subject


class BaseConnector(ABC):
    """Contract all source connectors must implement.

    Each connector defines its own ORM model (e.g. OpenNeuroDataset) in the
    same module as the connector. normalize_dataset returns that source-specific
    model instance. The ingest runner writes both a DatasetIndex row and the
    source-specific row per dataset.
    """

    SOURCE_NAME: str  # subclasses set this as a class attribute

    @abstractmethod
    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        """Yield raw dataset dicts from the source API."""

    @abstractmethod
    def get_source_id(self, raw: dict) -> str:
        """Extract the source-native identifier string from a raw record."""

    @abstractmethod
    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> Any:
        """Map a raw source dict to this connector's ORM model (not yet committed).
        Returns an instance of the source-specific model (e.g. OpenNeuroDataset).
        index_id is the DatasetIndex.id already written by the ingest runner.
        """

    @abstractmethod
    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        """Yield raw subject dicts for a given dataset."""

    @abstractmethod
    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        """Map a raw subject dict to a Subject ORM object.
        index_id references DatasetIndex, not any source-specific table.
        """
