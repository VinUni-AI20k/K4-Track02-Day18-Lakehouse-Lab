"""Record independent clean-environment PoC and required-lab checks locally."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
clean_python = REPO / "_lakehouse/bonus-clean-venv/Scripts/python.exe"
if not clean_python.exists():
    raise SystemExit("Create the dedicated clean verification venv with uv first.")
jobs = [
    ("clean-environment", [str(clean_python), "-X", "utf8", str(BASE / "poc/replay_safe.py")]),
    ("required-smoke", [sys.executable, "-X", "utf8", "scripts/verify_lite.py"]),
    ("required-pytest", [sys.executable, "-X", "utf8", "-m", "pytest", "-q"]),
    ("required-headless", [sys.executable, "-X", "utf8", "scripts/run_all.py"]),
    ("required-artifacts", [sys.executable, "-X", "utf8", "scripts/validate_submission.py"]),
]
results = []
for name, command in jobs:
    result = subprocess.run(command, cwd=REPO, encoding="utf-8", capture_output=True)
    log = "Command: " + " ".join(command) + "\n\nSTDOUT\n" + result.stdout + "\nSTDERR\n" + result.stderr
    (BASE / "evidence" / f"{name}.log").write_text(log, encoding="utf-8")
    results.append({"name": name, "exit_code": result.returncode})
    print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
(BASE / "evidence/local-checks.json").write_text(
    json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(), "checks": results}, indent=2) + "\n", encoding="utf-8")
assert all(r["exit_code"] == 0 for r in results), "Inspect the logs; do not mask failed checks"
