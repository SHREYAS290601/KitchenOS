from sqlalchemy import inspect
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class _TddProbe(Base):
    __tablename__ = "_tdd_probe"

    id: Mapped[int] = mapped_column(primary_key=True)


def test_tables_land_in_pantryops_schema(engine):
    Base.metadata.create_all(engine)
    tables = inspect(engine).get_table_names(schema="pantryops")
    assert "_tdd_probe" in tables
