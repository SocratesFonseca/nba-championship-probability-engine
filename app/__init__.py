"""Compatibility package for running the backend from the project root.

The real FastAPI package lives in backend/app. This shim lets commands such as
`uvicorn app.main:app` work from the repository root as well as from backend/.
"""

from pathlib import Path

_backend_app = Path(__file__).resolve().parents[1] / "backend" / "app"
if _backend_app.exists():
    __path__.append(str(_backend_app))