from neurodb.db import get_engine, get_session, init_db
from neurodb.schema import DatasetIndex, QualityEvent


def test_init_creates_schema():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 0
        assert session.query(QualityEvent).count() == 0
