"""Capture supplemental real output for version pin and vacuum dry-run."""
import html
import json
import os
from pathlib import Path
import subprocess

import nbformat
from execute_submission_safe import DATA, DEST, inside

profile = inside(DATA / "additional_evidence_browser")
temp = inside(DATA / "additional_evidence_temp")
assert not profile.exists() and not temp.exists()
profile.mkdir()
temp.mkdir()
nb = nbformat.read(DEST / "notebooks" / "08_agents_provenance.ipynb", as_version=4)
replay = "\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" and "json.dumps(training_run" in c.source for o in c.outputs if o.output_type == "stream")
assert "Replay at pinned version" in replay
plan = json.loads((DEST / "DESTRUCTIVE_REVIEW.json").read_text(encoding="utf-8"))
vacuum = plan["vacuum"]
review = json.dumps({"table": vacuum["table"], "version": vacuum["version"], "candidate_file_count": len(vacuum["files"]), "candidate_bytes": vacuum["total_bytes"], "measurement": "Sum of stat().st_size at canonical table_path / filename from VACUUM dry-run", "status": "NO FILES REMOVED; NOT RECLAIMED BYTES", "full_manifest": "submission/DESTRUCTIVE_REVIEW.json"}, ensure_ascii=False, indent=2)
for name, text in [("nb08_version_pin", replay), ("nb06_vacuum_candidates", review)]:
    page = inside(DEST / "evidence" / f"{name}.html")
    image = inside(DEST / "screenshots" / f"{name}.png")
    assert not page.exists() and not image.exists()
    with page.open("x", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><style>body{margin:40px;font:18px Arial;color:#182838}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px Consolas;line-height:1.6;background:#f5f8fc;padding:24px;border:1px solid #b9c8d8}</style><h1>' + name + '</h1><p>Bằng chứng bổ sung từ output/danh sách file thật. NB6–NB8 chưa hoàn tất.</p><pre>' + html.escape(text) + '</pre>')
    result = subprocess.run([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless", "--disable-gpu", "--no-first-run", "--disable-background-networking", "--disable-extensions", f"--user-data-dir={profile}", f"--screenshot={image}", "--window-size=1400,1100", "--hide-scrollbars", page.as_uri()], env=dict(os.environ, TEMP=str(temp), TMP=str(temp)), capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0 and image.is_file(), result.stderr[-1000:]
    print(image.name, image.stat().st_size, flush=True)
