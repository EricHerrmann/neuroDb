"""DB epoch — query helper functions over the DuckDB analytical store.

Migration target: src/neurodb/db/query.py
"""
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from neurodb.connectors.openneuro import OpenNeuroDataset


def search_datasets(
    session: Session,
    keyword: str | None = None,
    modality: str | None = None,
    source: str | None = None,
    limit: int = 200,
):
    """Search datasets across all sources using the v_all_datasets view."""
    conditions = []
    params: dict = {"limit": limit}

    if keyword:
        conditions.append(
            "(LOWER(title) LIKE :kw OR LOWER(COALESCE(description,'')) LIKE :kw)"
        )
        params["kw"] = f"%{keyword.lower()}%"
    if modality:
        conditions.append("LOWER(COALESCE(modality,'')) = LOWER(:modality)")
        params["modality"] = modality
    if source:
        conditions.append("source = :source")
        params["source"] = source

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = text(f"SELECT * FROM v_all_datasets {where} LIMIT :limit")  # noqa: S608
    return list(session.execute(sql, params).mappings())


def get_dataset_by_source_id(session: Session, source_id: str) -> OpenNeuroDataset | None:
    return session.execute(
        select(OpenNeuroDataset).where(OpenNeuroDataset.source_id == source_id)
    ).scalar_one_or_none()
