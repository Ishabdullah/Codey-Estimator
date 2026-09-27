import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "codey_estimator"

FORBIDDEN_MODULES = {
    "sqlite3",
    "socket",
    "urllib",
    "http",
    "requests",
    "datetime",
    "time",
    "random",
    "os",
    "subprocess",
    "io",
}


def _all_py_files():
    return list(SRC_ROOT.rglob("*.py"))


def _imported_module_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_no_forbidden_imports():
    for path in _all_py_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        imported = _imported_module_names(tree)
        forbidden_hit = imported & FORBIDDEN_MODULES
        assert not forbidden_hit, f"{path} imports forbidden modules: {forbidden_hit}"


def test_no_float_literals_in_calc():
    targets = [
        SRC_ROOT / "money.py",
        SRC_ROOT / "units.py",
        SRC_ROOT / "dto.py",
        *((SRC_ROOT / "calc").rglob("*.py")),
    ]
    for path in targets:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                raise AssertionError(f"{path} contains a float literal: {node.value}")
