"""DB epoch — provenance and lineage metadata helpers.

Migration target: src/neurodb/db/provenance.py
"""
from datetime import datetime, timezone
from sqlalchemy import Engine, select
from neurodb.db import get_session
from neurodb.schema import IngestRun, DatasetIndex
from neurodb.connectors.base import BaseConnector


def run_ingest(
    engine: Engine,
    connector: BaseConnector,
    limit: int = 100,
    dataset_ids: list[str] | None = None,
) -> IngestRun:
    """Fetch datasets from connector, upsert into DB, record provenance.

    Per dataset, two upserts occur:
    1. DatasetIndex — shared registry row (source + source_id unique key).
    2. Source-specific table — full native fields, referenced via index_id.
    """
    run = IngestRun(
        source=connector.SOURCE_NAME,
        run_at=datetime.now(timezone.utc).isoformat(),
        version=connector.VERSION,
    )
    with get_session(engine) as session:
        session.add(run)
        session.flush()

        source = (
            [connector.fetch_by_id(did) for did in dataset_ids]
            if dataset_ids is not None
            else connector.fetch_datasets(limit=limit)
        )
        for raw in source:
            source_id = connector.get_source_id(raw)

            # Step 1: Upsert DatasetIndex
            existing_idx = session.execute(
                select(DatasetIndex).where(
                    DatasetIndex.source == connector.SOURCE_NAME,
                    DatasetIndex.source_id == source_id,
                )
            ).scalar_one_or_none()

            if existing_idx:
                # DatasetIndex.run_id is immutable after creation (DuckDB rejects
                # UPDATE on rows referenced by a FK in another table).
                index_id = existing_idx.id
            else:
                idx = DatasetIndex(
                    source=connector.SOURCE_NAME,
                    source_id=source_id,
                    run_id=run.id,
                )
                session.add(idx)
                session.flush()
                index_id = idx.id

            # Step 2: Upsert source-specific record
            source_record = connector.normalize_dataset(raw, index_id=index_id, run_id=run.id)
            SourceModel = type(source_record)
            existing_src = session.execute(
                select(SourceModel).where(SourceModel.index_id == index_id)
            ).scalar_one_or_none()

            if existing_src:
                for attr, val in vars(source_record).items():
                    if not attr.startswith("_"):
                        setattr(existing_src, attr, val)
            else:
                session.add(source_record)

    return run
