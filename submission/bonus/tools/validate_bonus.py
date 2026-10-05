"""Check review artifacts; this does not award a grade or certify production."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import jupytext
import nbformat
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]
md = (BASE / "ARCHITECTURE.md").read_text(encoding="utf-8")
problem = md.split("## 1. Problem statement\n", 1)[1].split("###", 1)[0].strip()
assert len(problem.split()) <= 200
assert md.count("```text") == 1 and md.count("```") == 2
assert md.count("<!-- pagebreak -->") == 5
decisions = re.split(r"(?m)^### D\d\.", md)[1:]
assert len(decisions) == 6
for decision in decisions:
    text = decision.split("<!-- pagebreak -->")[0].split("## 4.")[0]
    assert "**Chọn:" in text and text.count("**Loại ") >= 2
failures = re.split(r"(?m)^### F\d\.", md)[1:]
assert len(failures) == 6
for failure in failures:
    assert "**Detect:" in failure and "**Recover/rollback:" in failure
assert "Day18 time travel" in md
pdf = PdfReader(BASE / "ARCHITECTURE.pdf")
assert len(pdf.pages) == 6
pdf_text = "\n".join(page.extract_text() for page in pdf.pages)
assert all(f"{i}. " in pdf.pages[i-1].extract_text() for i in range(1, 7))
assert "4.971,56" in pdf_text and "14.990,63" in pdf_text
assert "Hoàng Thái Đạt" in pdf_text

source = BASE / "poc/replay_safe.py"
source_lines = len(source.read_text(encoding="utf-8").splitlines())
assert 50 <= source_lines <= 150
original = jupytext.read(source, fmt="py:percent")
nb = nbformat.read(BASE / "poc/replay_safe.ipynb", as_version=4)
original_code = [c.source for c in original.cells if c.cell_type == "code"]
code = [c for c in nb.cells if c.cell_type == "code"]
assert [c.source for c in code] == original_code, "Executed notebook must match current source"
assert [c.execution_count for c in code] == list(range(1, len(code) + 1))
assert not any(o.output_type == "error" for c in code for o in c.outputs)
stdout = "".join(o.get("text", "") for c in code for o in c.outputs
                 if o.output_type == "stream" and o.name == "stdout")
actual = json.loads(next(s.split("=", 1)[1] for s in stdout.splitlines()
                         if s.startswith("BONUS_RESULT_JSON=")))
saved = json.loads((BASE / "evidence/poc-result.json").read_text())
assert saved["result"] == actual and saved["source_lines"] == source_lines
assert all(actual[k] for k in ("crash_after_commit", "stale_revision_ignored",
                              "conflicting_revision_blocked", "repeated_gold_equal"))
assert actual["replay_added_rows"] == 0 and actual["request_count"] == 2
assert actual["final_cost_micro_usd"] == 350 and actual["old_snapshot_cost_micro_usd"] == 300
cost = json.loads((BASE / "evidence/cost-model.json").read_text())
for case in [cost["base"], cost["month_31_days"], *cost["sensitivity"]]:
    d = lambda k: Decimal(str(case[k]))
    assert d("storage_usd") == sum(d(k) for k in ["s3_usd", "s3_requests_usd", "stream_usd", "storage_reserve_usd"])
    assert d("total_usd") == d("storage_usd") + d("compute_operations_usd")
    assert case["storage_cap_pass"] == (d("storage_usd") <= 5000)
assert cost["month_31_days"]["storage_cap_pass"]
assert all(not case["storage_cap_pass"] for case in cost["sensitivity"])

local_links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", md)
for link in local_links:
    if not link.startswith(("https://", "http://", "#")):
        assert (BASE / link).exists(), f"Broken local link: {link}"
for name in ["README.md", "requirements-bonus.txt", "evidence/clean-environment.log"]:
    assert (BASE / name).exists()
report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
          "status": "PASS", "problem_statement_words_whitespace": len(problem.split()),
          "pdf_pages": len(pdf.pages), "diagrams": 1, "decisions": len(decisions),
          "minimum_rejected_alternatives_per_decision": 2, "failure_modes": len(failures),
          "poc_source_lines": source_lines, "poc_code_cells_executed": len(code),
          "executed_notebook_matches_source": True, "poc_result": actual,
          "storage_month_31_usd": cost["month_31_days"]["storage_usd"],
          "sensitivity_failures_reported": len(cost["sensitivity"]),
          "limitation": "Structure/arithmetic/output checks, not rubric grading or AWS load/security validation"}
(BASE / "evidence/validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
hashes = {p.relative_to(BASE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(BASE.rglob("*")) if p.is_file()
          and p.name != "artifact-sha256.json" and "__pycache__" not in p.parts}
(BASE / "evidence/artifact-sha256.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
