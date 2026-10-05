"""Build and execute all 8 lightweight notebooks, saving outputs to submission/notebooks/."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"
SUB_NB_DIR = ROOT / "submission" / "notebooks"
SUB_NB_DIR.mkdir(parents=True, exist_ok=True)

notebooks = sorted(p for p in NB_DIR.glob("[0-9]*.py"))
print(f"Found {len(notebooks)} notebooks to build and execute.")

for nb_py in notebooks:
    nb_name = nb_py.stem
    nb_ipynb = NB_DIR / f"{nb_name}.ipynb"
    target_ipynb = SUB_NB_DIR / f"{nb_name}.ipynb"
    
    print(f"\n--- Processing {nb_name} ---")
    
    # 1. Convert .py to .ipynb via jupytext
    print(f"Converting {nb_py.name} -> {nb_ipynb.name}")
    cmd_jupytext = [
        sys.executable, "-m", "jupytext",
        "--to", "notebook",
        str(nb_py), "-o", str(nb_ipynb)
    ]
    subprocess.run(cmd_jupytext, check=True)
    
    # 2. Execute notebook via nbconvert
    print(f"Executing {nb_ipynb.name} inplace...")
    cmd_nbconvert = [
        sys.executable, "-m", "jupyter", "nbconvert",
        "--to", "notebook",
        "--execute",
        "--inplace",
        "--ExecutePreprocessor.timeout=300",
        str(nb_ipynb)
    ]
    proc = subprocess.run(cmd_nbconvert, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"FAILED executing {nb_ipynb.name}:")
        print(proc.stdout)
        print(proc.stderr)
        sys.exit(proc.returncode)
    print(f"Successfully executed {nb_ipynb.name}")
    
    # 3. Copy to submission/notebooks/
    shutil.copy2(nb_ipynb, target_ipynb)
    print(f"Copied to {target_ipynb}")

print(f"\n[DONE] All {len(notebooks)} notebooks built, executed and copied to submission/notebooks/!")
