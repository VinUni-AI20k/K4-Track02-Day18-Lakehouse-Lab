"""Render a new NB6 completion artifact from recorded actual measurements."""
import html
import json
import os
from pathlib import Path
import subprocess

import nbformat

from prepare_remaining_review import DATA, DEST, fresh, scoped, write_new


def main():
    log = json.loads((DEST / "logs" / "nb6_completed_20261004.json").read_text(encoding="utf-8"))
    assert all(log["checks"].values()) and len(log["checks"]) == 9
    nb = nbformat.read(DEST / "notebooks" / "06_maintenance.ipynb", as_version=4)
    assert nb.metadata["lab_execution_status"] == "complete"
    assertion = next(c for c in nb.cells if c.cell_type == "code" and "assert all(checks.values())" in c.source)
    output = "".join(o.get("text", "") for o in assertion.outputs)
    assert output.count("[PASS]") == 9 and "NB6 complete." in output
    summary = {k: v for k, v in log.items() if k not in {"checks", "review_sha256", "authorization_scope"}}
    body = json.dumps(summary, ensure_ascii=False, indent=2) + "\n\n" + output
    page = fresh(DEST / "evidence" / "nb06_completed_20261004.html")
    image = fresh(DEST / "screenshots" / "nb06_completed_20261004.png")
    runtime = fresh(DATA / "evidence_nb6_completed_20261004")
    content = ('<!doctype html><html lang="vi"><meta charset="utf-8"><title>NB6 complete</title>'
               '<style>body{margin:32px;color:#17212b;font:17px Arial}h1{font-size:26px}pre{white-space:pre-wrap;font:15px Consolas;line-height:1.4;padding:20px;background:#f5f8fc;border:1px solid #bdccdb}</style>'
               '<h1>NB6 — VACUUM / expiry / sweep: 9 assertion gốc PASS</h1>'
               '<p>04/10/2026 — Bằng chứng xuất từ output thật; không phải giao diện Jupyter.</p><pre>'
               + html.escape(body) + '</pre><p>Nguồn: submission/logs/nb6_completed_20261004.json và submission/notebooks/06_maintenance.ipynb</p></html>')
    write_new(page, content)
    runtime.mkdir()
    profile = scoped(runtime / "browser")
    temp = scoped(runtime / "temp")
    profile.mkdir()
    temp.mkdir()
    proc = subprocess.run([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless", "--disable-gpu",
                           "--no-first-run", "--disable-background-networking", "--disable-extensions",
                           f"--user-data-dir={profile}", f"--screenshot={image}",
                           f"--window-size=1400,{max(1000, 250+len(body.splitlines())*23)}", "--hide-scrollbars", page.as_uri()],
                          env=dict(os.environ, TEMP=str(temp), TMP=str(temp)),
                          capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    assert proc.returncode == 0 and image.is_file(), proc.stderr[-1000:]
    print(image.name, image.stat().st_size)


if __name__ == "__main__":
    main()
