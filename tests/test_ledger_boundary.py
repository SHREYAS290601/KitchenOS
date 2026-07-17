"""Invariant 1 as a test: the ledger service is the only pantry write path.

Walks backend/app with ast and rejects any module (outside the allow-list)
that assigns to a PantryItem sourced-field attribute or constructs
LedgerChangeLog directly. Routes must go through apply_update.
"""

import ast
from pathlib import Path

from backend.app.models.pantry_item import SOURCED_FIELD_COLUMNS

BACKEND_APP = Path(__file__).resolve().parents[1] / "backend" / "app"

# The single write path and the model definitions themselves.
ALLOWED = ("services/ledger.py", "models/")

SOURCED_FIELDS = set(SOURCED_FIELD_COLUMNS)


def _is_allowed(path: Path) -> bool:
    relative = path.relative_to(BACKEND_APP).as_posix()
    return relative.startswith(ALLOWED)


def _app_modules() -> list[Path]:
    return [path for path in BACKEND_APP.rglob("*.py") if not _is_allowed(path)]


def test_no_sourced_field_assignment_outside_ledger():
    violations: list[str] = []
    for path in _app_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in SOURCED_FIELDS:
                    violations.append(
                        f"{path.relative_to(BACKEND_APP)}:{node.lineno} "
                        f"assigns .{target.attr} directly — use apply_update()"
                    )
    assert violations == []


def test_no_direct_change_log_construction_outside_ledger():
    violations: list[str] = []
    for path in _app_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name == "LedgerChangeLog":
                violations.append(
                    f"{path.relative_to(BACKEND_APP)}:{node.lineno} "
                    "constructs LedgerChangeLog directly — only the ledger service may"
                )
    assert violations == []


def test_pantry_routes_import_apply_update_not_orm_helpers():
    tree = ast.parse((BACKEND_APP / "routes" / "pantry.py").read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert "apply_update" in imported, "routes/pantry.py must write via apply_update"
    assert "LedgerChangeLog" not in imported, (
        "routes/pantry.py must not touch the change log ORM model directly"
    )


def test_agents_do_not_import_ledger_write_helpers():
    violations = []
    for path in (BACKEND_APP / "agents").glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module == "backend.app.services.ledger"
                or (node.module or "").startswith("backend.app.models")
            ):
                violations.append(path.name)
    assert violations == []
