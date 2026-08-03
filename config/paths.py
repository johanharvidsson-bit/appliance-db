from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(os.getenv("REPAIRBASE_BASE_DIR", Path(__file__).resolve().parent.parent)).resolve()


def resolve_project_path(value: str, default: str) -> Path:
    path = Path(value or default)
    return path if path.is_absolute() else BASE_DIR / path
