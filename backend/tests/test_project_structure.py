import sys
from pathlib import Path


def test_python_version() -> None:
    assert sys.version_info >= (3, 12), f"Expected Python >= 3.12, got {sys.version_info}"


def test_project_structure() -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    backend_dir = root_dir / "backend"
    app_dir = backend_dir / "app"

    assert backend_dir.exists(), "backend directory does not exist"
    assert app_dir.exists(), "backend/app directory does not exist"
    assert (app_dir / "__init__.py").exists(), "backend/app/__init__.py does not exist"
