from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from neurodb.connectors.openneuro import OpenNeuroDataset

# TODO (Phase 3): search_datasets and get_dataset_by_id are coupled to OpenNeuroDataset.
# When a second source connector is added, refactor to accept a model class or
# query the shared DatasetIndex table instead.


def search_datasets(
    session: Session,
    keyword: str | None = None,
    modality: str | None = None,
    limit: int = 200,
) -> list[OpenNeuroDataset]:
    stmt = select(OpenNeuroDataset)
    if keyword:
        term = f"%{keyword.lower()}%"
        stmt = stmt.where(
            or_(
                OpenNeuroDataset.title.ilike(term),
                OpenNeuroDataset.description.ilike(term),
            )
        )
    if modality:
        stmt = stmt.where(OpenNeuroDataset.modality.ilike(modality))
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars())


def get_dataset_by_source_id(session: Session, source_id: str) -> OpenNeuroDataset | None:
    return session.execute(
        select(OpenNeuroDataset).where(OpenNeuroDataset.source_id == source_id)
    ).scalar_one_or_none()
