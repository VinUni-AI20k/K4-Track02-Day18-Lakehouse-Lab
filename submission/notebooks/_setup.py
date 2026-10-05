"""Path bootstrap for notebooks when executed inside submission/notebooks.

Resolves `scripts/lakehouse.py` from the repo root regardless of where
Jupyter / Python was launched from.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] if _HERE.parent.name == "submission" else _HERE.parent
_DOCKER = Path("/workspace/scripts")
_LOCAL = _ROOT / "scripts"

_TARGET = _DOCKER if _DOCKER.exists() else _LOCAL
if str(_TARGET) not in sys.path:
    sys.path.insert(0, str(_TARGET))
