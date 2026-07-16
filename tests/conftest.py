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


@pytest.fixture(autouse=True)
def eager_celery():
    from backend.app.workers.celery_app import celery

    previous = {
        "task_always_eager": celery.conf.task_always_eager,
        "task_eager_propagates": celery.conf.task_eager_propagates,
        "task_store_eager_result": celery.conf.task_store_eager_result,
    }
    celery.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_store_eager_result=False,
    )
    yield celery
    celery.conf.update(**previous)


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


@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    return engine
