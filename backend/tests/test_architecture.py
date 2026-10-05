"""Guard the dependency direction of each business module."""

import ast
from pathlib import Path


MODULES = Path(__file__).resolve().parents[1] / "app" / "modules"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }


def test_business_rules_depend_inward_only():
    for path in MODULES.rglob("*.py"):
        if not (path.name == "domain.py" or path.name.endswith("ports.py") or path.name.endswith("application.py")):
            continue
        for module in imported_modules(path):
            assert not module.startswith(("fastapi", "sqlalchemy", "app.api", "app.http",
                                          "app.infrastructure")), (path, module)
            assert ".infrastructure" not in module and ".file_parser" not in module, (path, module)


def test_http_adapters_do_not_access_orm():
    for path in MODULES.rglob("*.py"):
        if path.name not in {"api.py", "auth_api.py", "admin_api.py", "accounts_api.py",
                             "categories_api.py", "transactions_api.py", "scenarios_api.py"}:
            continue
        for module in imported_modules(path):
            assert not module.startswith(("sqlalchemy", "app.infrastructure.models")), (path, module)


def test_sql_adapters_do_not_invoke_use_cases():
    for path in MODULES.rglob("*infrastructure.py"):
        for module in imported_modules(path):
            assert not module.endswith(".application"), (path, module)
            assert not module.endswith("_application"), (path, module)


def test_ledger_store_does_not_query_other_domains():
    path = MODULES / "ledger" / "infrastructure.py"
    tree = ast.parse(path.read_text())
    models = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "app.infrastructure.models"
        for alias in node.names
    }
    assert models <= {"Account", "Category", "Transaction", "UserSettings"}


def test_business_modules_do_not_import_compatibility_api():
    for path in MODULES.rglob("*.py"):
        for module in imported_modules(path):
            assert not module.startswith(("app.api", "app.application", "app.domain")), (path, module)


def test_sql_adapters_only_import_infrastructure_of_their_own_domain():
    for path in MODULES.rglob("*infrastructure.py"):
        domain = path.parent.name
        for module in imported_modules(path):
            if module.startswith("app.modules.") and ".infrastructure" in module:
                assert module.split(".")[2] == domain, (path, module)
