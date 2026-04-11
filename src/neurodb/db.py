from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import Session

from neurodb.schema import Base


def get_engine(url: str = "sqlite:///neurodb.db") -> Engine:
    return _create_engine(url, echo=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
        session.commit()
