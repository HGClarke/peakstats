"""Guard tests that enforce the layering rules documented in CLAUDE.md.

These keep the architecture self-checking: if someone imports `fastapi` into a
service, or reaches across a layer, the suite fails instead of relying on review.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def _imports(path: Path) -> set[str]:
    """Return the set of module names imported by a Python file."""
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _modules(*parts: str) -> list[Path]:
    return sorted(APP.joinpath(*parts).glob("*.py"))


def test_services_do_not_import_fastapi() -> None:
    for path in _modules("services"):
        imports = _imports(path)
        offenders = {i for i in imports if i == "fastapi" or i.startswith("fastapi.")}
        assert not offenders, (
            f"{path.name} imports {offenders}; services must stay framework-agnostic"
        )


def test_routers_do_not_import_db_directly() -> None:
    for path in _modules("routers"):
        imports = _imports(path)
        offenders = {i for i in imports if i == "app.db" or i.startswith("app.db.")}
        assert not offenders, (
            f"{path.name} imports {offenders}; routers must go through services"
        )


def test_db_does_not_import_upper_layers() -> None:
    for path in _modules("db"):
        imports = _imports(path)
        offenders = {
            i for i in imports if i.startswith(("app.services", "app.routers"))
        }
        assert not offenders, (
            f"{path.name} imports {offenders}; db must stay the bottom layer"
        )
