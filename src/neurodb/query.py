from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from neurodb.connectors.openneuro import OpenNeuroDataset


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
        stmt = stmt.where(OpenNeuroDataset.modality == modality)
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars())


def get_dataset_by_id(session: Session, dataset_id: int) -> OpenNeuroDataset | None:
    return session.get(OpenNeuroDataset, dataset_id)
