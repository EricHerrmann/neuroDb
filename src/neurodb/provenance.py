from datetime import datetime, timezone
from sqlalchemy import Engine, select
from neurodb.db import get_session
from neurodb.schema import IngestRun, DatasetIndex
from neurodb.connectors.base import BaseConnector


def run_ingest(engine: Engine, connector: BaseConnector, limit: int = 100) -> IngestRun:
    """Fetch datasets from connector, upsert into DB, record provenance.

    Per dataset, two upserts occur:
    1. DatasetIndex — shared registry row (source + source_id unique key).
    2. Source-specific table — full native fields, referenced via index_id.
    """
    run = IngestRun(
        source=connector.SOURCE_NAME,
        run_at=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
    )
    with get_session(engine) as session:
        session.add(run)
        session.flush()

        for raw in connector.fetch_datasets(limit=limit):
            source_id = connector.get_source_id(raw)

            # Step 1: Upsert DatasetIndex
            existing_idx = session.execute(
                select(DatasetIndex).where(
                    DatasetIndex.source == connector.SOURCE_NAME,
                    DatasetIndex.source_id == source_id,
                )
            ).scalar_one_or_none()

            if existing_idx:
                existing_idx.run_id = run.id
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
