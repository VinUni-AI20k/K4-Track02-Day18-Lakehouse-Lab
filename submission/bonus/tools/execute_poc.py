"""Execute the source through a real kernel; retain outputs and their provenance."""
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone

import jupytext
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
source = BASE / "poc/replay_safe.py"
nb = jupytext.read(source, fmt="py:percent")
os.environ.setdefault("JUPYTER_RUNTIME_DIR", str(REPO / "_lakehouse/bonus-jupyter-runtime"))
Path(os.environ["JUPYTER_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
km = KernelManager(kernel_name="python3")
km.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
client = NotebookClient(nb, km=km, timeout=120,
                        resources={"metadata": {"path": str(REPO)}}, record_timing=True)
client.execute()
code_cells = [c for c in nb.cells if c.cell_type == "code"]
assert all(c.execution_count is not None for c in code_cells)
assert not any(o.output_type == "error" for c in code_cells for o in c.outputs)
stdout = "".join(o.get("text", "") for c in code_cells for o in c.outputs
                 if o.output_type == "stream" and o.name == "stdout")
result = json.loads(next(line.split("=", 1)[1] for line in stdout.splitlines()
                         if line.startswith("BONUS_RESULT_JSON=")))
nb.metadata["bonus_execution"] = {"python": platform.python_version(),
                                   "executed_at_utc": datetime.now(timezone.utc).isoformat()}
nbformat.write(nb, BASE / "poc/replay_safe.ipynb")
evidence = {"result": result, "code_cells_executed": len(code_cells),
            "source_lines": len(source.read_text(encoding="utf-8").splitlines()),
            "execution": nb.metadata["bonus_execution"], "stdout": stdout}
(BASE / "evidence/poc-result.json").write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"PASS: {len(code_cells)} cells, {evidence['source_lines']} source lines, no error outputs")
print(stdout)
