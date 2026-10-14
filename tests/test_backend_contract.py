from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from ironkit.backends import Backend

BACKENDS = Path(__file__).resolve().parents[1] / "src" / "ironkit" / "backends"
CLASSES = {
    "fake.py": "FakeBackend",
    "x11.py": "X11Backend",
    "windows.py": "WindowsBackend",
    "macos.py": "MacBackend",
}


def protocol_methods() -> dict[str, list[str]]:
    methods: dict[str, list[str]] = {}
    for name, member in inspect.getmembers(Backend, inspect.isfunction):
        if not name.startswith("_"):
            methods[name] = list(inspect.signature(member).parameters)
    return methods


def class_methods(path: Path, class_name: str) -> dict[str, list[str]]:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name: [a.arg for a in item.args.args] for item in node.body if isinstance(item, ast.FunctionDef)
            }
    raise AssertionError(f"{class_name} not found in {path.name}")


@pytest.mark.parametrize(("filename", "class_name"), sorted(CLASSES.items()))
def test_backend_implements_protocol(filename: str, class_name: str) -> None:
    implemented = class_methods(BACKENDS / filename, class_name)
    for name, params in protocol_methods().items():
        assert name in implemented, f"{class_name} is missing {name}()"
        assert implemented[name] == params, f"{class_name}.{name} has parameters {implemented[name]}, expected {params}"


@pytest.mark.parametrize(("filename", "class_name"), sorted(CLASSES.items()))
def test_backend_declares_name_and_capabilities(filename: str, class_name: str) -> None:
    source = (BACKENDS / filename).read_text()
    assert f'name = "{filename.removesuffix(".py")}"' in source
    assert "self.capabilities = " in source
