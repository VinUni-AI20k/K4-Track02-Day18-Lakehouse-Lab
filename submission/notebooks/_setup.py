"""Path bootstrap for notebooks, works whether running from notebooks/ or submission/notebooks/."""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# Find repo root by locating scripts/
for parent in [_HERE, _HERE.parent, _HERE.parent.parent]:
    scripts_dir = parent / "scripts"
    if scripts_dir.exists():
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        break
