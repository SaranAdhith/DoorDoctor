"""Phase 12 — the intelligence layers sit beside the platform, never inside it.

The existing application may import `app.intelligence` from exactly the modules
listed here. Anything else reaching into it — a model, a core module, an
existing service — is how "switch a layer off" quietly stops being true, so it
fails here rather than in review. (`app.main` registers the Phase 12 routers but
imports the router modules, not the package, so it is not on the list.)

The reverse direction is unrestricted on purpose: the layers exist to read the
platform.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

#: module → why it may import the intelligence package.
ALLOWED_IMPORTERS: dict[str, str] = {
    "app.scheduler": "runs the document worker",
    "app.services.privacy_service": "registers Phase 12 datasets so erasure covers them",
    "app.routers.documents": "a Phase 12 router",
}


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(APP.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    module = _module_name(path)
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".")
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts)
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            found.add(target)
            found.update(f"{target}.{alias.name}" for alias in node.names)
    return found


def _reaches_intelligence(imports: set[str]) -> bool:
    return any(name == "app.intelligence" or name.startswith("app.intelligence.") for name in imports)


def test_only_the_named_modules_import_the_intelligence_package():
    offenders = []
    for path in APP.rglob("*.py"):
        if "intelligence" in path.relative_to(APP).parts[:1]:
            continue  # the package itself
        module = _module_name(path)
        if _reaches_intelligence(_imports(path)) and module not in ALLOWED_IMPORTERS:
            offenders.append(module)
    assert not offenders, (
        f"{sorted(offenders)} import app.intelligence. Add the module to "
        "ALLOWED_IMPORTERS with a reason, or move the dependency the other way."
    )


def test_every_allowed_importer_still_exists_and_still_needs_to():
    """A stale allowance is a hole someone else walks through later."""
    for module in ALLOWED_IMPORTERS:
        path = APP.parent / Path(*module.split(".")).with_suffix(".py")
        assert path.is_file(), f"{module} no longer exists; drop it from ALLOWED_IMPORTERS"
        assert _reaches_intelligence(_imports(path)), f"{module} no longer imports app.intelligence"


def test_the_resolver_understands_relative_imports():
    """The test is only as good as its import resolution."""
    path = APP / "services" / "privacy_service.py"
    assert "app.intelligence.documents" in _imports(path)


def test_core_intelligence_imports_nothing_from_the_application():
    tree = ast.parse((APP / "core" / "intelligence.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and not (node.module or "").startswith("app"), node.module
        elif isinstance(node, ast.Import):
            assert all(not alias.name.startswith("app") for alias in node.names)
