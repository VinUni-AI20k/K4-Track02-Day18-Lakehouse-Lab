"""Execute every notebook headlessly, in order. `make run-all`.

Runs the lightweight Python notebooks and any assertions they contain.
A non-zero exit indicates a runtime or assertion failure. Passing does not
prove every rubric criterion, and this runner does not save .ipynb outputs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"


def main() -> int:
    notebooks = sorted(p for p in NB_DIR.glob("*.py") if not p.name.startswith("_"))
    if not notebooks:
        print("No notebooks found.")
        return 1

    # Force UTF-8 encoding for subprocess stdout/stderr to avoid
    # UnicodeEncodeError on Windows cp1252 consoles.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    print(f"Running {len(notebooks)} notebooks with {sys.executable}\n")
    failures, total = [], 0.0
    for nb in notebooks:
        t0 = time.perf_counter()
        proc = subprocess.run([sys.executable, str(nb)], capture_output=True, text=True, env=env, encoding="utf-8")
        dt = time.perf_counter() - t0
        total += dt
        if proc.returncode == 0:
            print(f"  PASS  {nb.name:<32} {dt:6.1f}s")
        else:
            print(f"  FAIL  {nb.name:<32} {dt:6.1f}s")
            failures.append((nb.name, proc.stdout[-1500:], proc.stderr[-1500:]))

    print(f"\n{len(notebooks) - len(failures)}/{len(notebooks)} passed in {total:.1f}s")
    for name, out, err in failures:
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        print(out)
        print(err)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
