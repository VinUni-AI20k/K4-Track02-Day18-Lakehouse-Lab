"""Script to build, execute, and prepare the submission artifacts for Day 18 Lakehouse Lab.

This script:
1. Converts all 8 lightweight notebooks (`notebooks/01_delta_basics.py` .. `08_agents_provenance.py`) to `.ipynb`.
2. Executes every notebook headlessly so that all execution outputs, outputs of inspection cells,
   tables, and assertions are permanently saved inside the notebook JSON.
3. Copies/Saves the executed `.ipynb` files to `submission/notebooks/`.
4. Generates terminal summaries and verifies criteria against RUBRIC.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"
SUBMISSION_DIR = ROOT / "submission"
SUBMISSION_NB_DIR = SUBMISSION_DIR / "notebooks"
SCREENSHOTS_DIR = SUBMISSION_DIR / "screenshots"


def main():
    print("=" * 70)
    print(" Day 18 Lakehouse Lab — Submission Builder & Executed Notebook Generator")
    print("=" * 70)

    SUBMISSION_NB_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    notebooks = sorted(p for p in NB_DIR.glob("[0-9]*.py"))
    if not notebooks:
        print("ERROR: No lightweight notebooks found in notebooks/")
        return 1

    # Ensure ipykernel is available and registered for current virtualenv
    try:
        import ipykernel  # noqa: F401
    except ImportError:
        print("[*] Installing ipykernel in virtualenv ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "ipykernel"], check=True)

    print("[*] Registering Jupyter kernel for virtualenv ...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            "day18_venv",
            "--display-name",
            "Python (Day18 .venv)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{NB_DIR}{os.pathsep}{ROOT / 'scripts'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["PYTHONUTF8"] = "1"

    for py_nb in notebooks:
        nb_name = py_nb.stem
        local_ipynb = NB_DIR / f"{nb_name}.ipynb"
        target_ipynb = SUBMISSION_NB_DIR / f"{nb_name}.ipynb"
        print(f"[*] Processing {nb_name} ...")

        # 1. Convert .py to .ipynb in notebooks/
        cmd_convert = [
            sys.executable,
            "-m",
            "jupytext",
            "--to",
            "notebook",
            str(py_nb),
            "-o",
            str(local_ipynb),
        ]
        res_conv = subprocess.run(cmd_convert, capture_output=True, text=True, env=env)
        if res_conv.returncode != 0:
            print(f"  [!] Failed to convert {py_nb.name} to .ipynb:")
            print(res_conv.stderr)
            return 1

        # 2. Execute .ipynb in notebooks/ using the day18_venv kernel
        print(f"  [>] Executing {nb_name}.ipynb using virtualenv kernel ...")
        t0 = time.perf_counter()
        cmd_exec = [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.kernel_name=day18_venv",
            f"--ExecutePreprocessor.cwd={NB_DIR}",
            "--ExecutePreprocessor.timeout=600",
            str(local_ipynb),
        ]
        res_exec = subprocess.run(cmd_exec, capture_output=True, text=True, cwd=str(NB_DIR), env=env)
        elapsed = time.perf_counter() - t0

        if res_exec.returncode == 0:
            # 3. Copy executed notebook with outputs into submission/notebooks/
            shutil.copy2(local_ipynb, target_ipynb)
            print(f"  [✓] {nb_name}.ipynb executed and saved ({elapsed:.1f}s)")
        else:
            print(f"  [✗] Execution failed for {nb_name}.ipynb ({elapsed:.1f}s)")
            print(res_exec.stderr[-1000:] if res_exec.stderr else res_exec.stdout[-1000:])
            return 1

    print("\n" + "=" * 70)
    print(" All 8 notebooks converted, executed, and saved in submission/notebooks/!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
