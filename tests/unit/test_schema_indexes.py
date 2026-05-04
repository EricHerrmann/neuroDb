from sqlalchemy import create_engine, inspect

from neurodb.db import init_db


def test_quality_events_has_compound_index():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    indexes = inspect(engine).get_indexes("quality_events")
    index_column_sets = [
        frozenset(idx["column_names"]) for idx in indexes
    ]
    assert frozenset({"entity_source", "entity_id", "flag"}) in index_column_sets, (
        "Expected compound index on (entity_source, entity_id, flag) in quality_events"
    )
