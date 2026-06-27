"""Back-compat shim. Implementation moved to neurodb.literature.

Existing imports (`from neurodb.literature_client import LiteratureSearchClient`)
keep working; new code should import from `neurodb.literature`.
"""
from neurodb.literature import LiteratureSearchClient

__all__ = ["LiteratureSearchClient"]
