"""Ranh giới import: doc_ingest là tool offline, tách khỏi dịch vụ chat theo cả hai chiều."""
import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOC_INGEST = APP_ROOT / "modules" / "doc_ingest"
PACKAGE = "app.modules.doc_ingest"
HEAVY_LIBS = {"docling", "docling_core", "pypdfium2", "PIL"}
HEAVY_ALLOWED = (DOC_INGEST / "parse", DOC_INGEST / "spike")


def _absolute_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _rel(path: Path) -> str:
    return path.relative_to(APP_ROOT.parent).as_posix()


def test_doc_ingest_only_imports_its_own_app_package() -> None:
    violations = [
        f"{_rel(path)}: {name}"
        for path in _python_files(DOC_INGEST)
        for name in _absolute_imports(path)
        if name.split(".")[0] == "app" and not (name == PACKAGE or name.startswith(PACKAGE + "."))
    ]
    assert violations == []


def test_rest_of_app_does_not_import_doc_ingest() -> None:
    violations = [
        f"{_rel(path)}: {name}"
        for path in _python_files(APP_ROOT)
        if DOC_INGEST not in path.parents
        for name in _absolute_imports(path)
        if name == PACKAGE or name.startswith(PACKAGE + ".")
    ]
    assert violations == []


def test_heavy_libs_only_in_parse_and_spike() -> None:
    violations = [
        f"{_rel(path)}: {name}"
        for path in _python_files(APP_ROOT)
        if not any(allowed in path.parents for allowed in HEAVY_ALLOWED)
        for name in _absolute_imports(path)
        if name.split(".")[0] in HEAVY_LIBS
    ]
    assert violations == []
