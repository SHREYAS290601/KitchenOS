import os

import pytest
from sqlalchemy import text

from backend.app.db import Base, make_engine, make_session_factory

TEST_DATABASE_URL = os.environ.get(
    "PANTRYOPS_TEST_DATABASE_URL",
    "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
)


@pytest.fixture(scope="session")
def engine():
    eng = make_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        conn.execute(text('DROP SCHEMA IF EXISTS pantryops CASCADE'))
        conn.execute(text('CREATE SCHEMA pantryops'))
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    session_factory = make_session_factory(engine)
    session = session_factory()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()
