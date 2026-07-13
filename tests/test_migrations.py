import json
import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from tests.conftest import TEST_DATABASE_URL

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_head_matches_metadata():
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS pantryops CASCADE"))
        conn.execute(text("CREATE SCHEMA pantryops"))

    env = {**os.environ, "PANTRYOPS_DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
    )

    insp = inspect(eng)
    db_tables = {
        table: sorted(col["name"] for col in insp.get_columns(table, schema="pantryops"))
        for table in insp.get_table_names(schema="pantryops")
        if table != "alembic_version"
    }
    eng.dispose()

    dump_metadata = (
        "import json; from backend.app.db import Base; "
        "print(json.dumps({t.name: sorted(c.name for c in t.columns) "
        "for t in Base.metadata.sorted_tables}))"
    )
    out = subprocess.run(
        ["uv", "run", "python", "-c", dump_metadata],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    metadata_tables = json.loads(out.stdout)

    assert db_tables == metadata_tables
