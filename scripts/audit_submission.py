"""Read-only readiness audit; does not rerun/reset data or publish anything."""
import json
from pathlib import Path
import re
import struct

import nbformat
from execute_submission_safe import DEST, inside

notebooks = []
for p in sorted((DEST / "notebooks").glob("*.ipynb")):
    nb = nbformat.read(p, as_version=4)
    nbformat.validate(nb)
    errors = [o.ename for c in nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "error"]
    assert not errors
    assert any(c.cell_type == "markdown" and c.source.startswith("### Trả lời câu hỏi thử thách") for c in nb.cells)
    notebooks.append({"name": p.name, "status": nb.metadata["lab_execution_status"], "error_outputs": errors})
assert len(notebooks) == 8
images = []
for p in sorted((DEST / "screenshots").glob("*.png")):
    data = p.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width > 0 and height > 0
    images.append({"name": p.name, "width": width, "height": height, "bytes": len(data)})
assert all(any(x["name"].startswith(f"nb{i:02d}_") for x in images) for i in range(1, 9))
words = len((DEST / "REFLECTION.md").read_text(encoding="utf-8").split())
assert words <= 200
credential_patterns = re.compile(r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}|sk-proj-[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)")
findings = []
for p in DEST.rglob("*"):
    if p.is_file() and p.suffix in {".md", ".json", ".ipynb", ".txt", ".html", ".xml"}:
        if credential_patterns.search(p.read_text(encoding="utf-8")):
            findings.append(str(p.relative_to(DEST)))
assert not findings, "Credential-like content needs manual inspection"
report = {"notebooks": notebooks, "screenshots": images, "reflection_word_count": words,
          "credential_pattern_findings": findings, "scan_limit": "Only selected common credential patterns; not a guarantee of absence.",
          "ready_to_submit": False, "blockers": ["NB6–NB8 destructive cells await direct authorization under the user's AGENTS policy", "Full smoke 9/9, pytest 24/24 and runner 8/8 have not completed"],
          "publication": "Not staged, committed, pushed or submitted as a completed lab."}
with inside(DEST / "logs" / "submission_audit.json").open("x", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"Validated {len(notebooks)} notebooks, {len(images)} PNGs, reflection {words} words. Ready to submit: False.")
