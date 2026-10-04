"""Render supplemental HTML evidence and PNGs from actual saved outputs.

Uses headless Chrome as an artifact renderer, with a new workspace-local
profile/temp directory. Never opens or modifies the user's browser profile.
Previous evidence is retained. No notebook execution or data deletion.
"""
import html
import json
import os
from pathlib import Path
import subprocess

import nbformat

from prepare_remaining_review import DATA, DEST, fresh, scoped, write_new


def main():
    browser = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    assert browser.is_file()
    runtime = fresh(DATA / "evidence_resumed_20261004_retry")
    items = []
    prep = json.loads((DEST / "logs" / "preparation_20261004.json").read_text(encoding="utf-8"))
    summary = {k: v for k, v in prep.items() if k not in {"subject_rows_before_delete", "automatic_checkpoint", "checkpoint_files"}}
    summary["note"] = "NB6 BASELINE ONLY: no VACUUM, expiry or orphan removal; NOT a final PASS."
    items.append(("nb06_preparation_20261004", "NB6 — baseline; chưa hoàn tất", json.dumps(summary, ensure_ascii=False, indent=2), "submission/logs/preparation_20261004.json"))
    for name, number, markers in [("07_vectors_multimodal", 7, ["Erasure request for", "Erased docs still", "CDF rows since", "NB7 complete."]),
                                  ("08_agents_provenance", 8, ["Rows for user_007", "NB8 complete."])]:
        notebook = scoped(DEST / "notebooks" / f"{name}.ipynb")
        nb = nbformat.read(notebook, as_version=4)
        assert nb.metadata["lab_execution_status"] == "complete"
        texts = []
        for cell in nb.cells:
            if cell.cell_type == "code":
                text = "".join(o.get("text", "") for o in cell.outputs if o.output_type == "stream")
                if any(marker in text for marker in markers):
                    texts.append(text.strip())
        body = "\n\n".join(texts)
        assert f"NB{number} complete." in body
        items.append((f"nb{number:02d}_completed_20261004", f"NB{number} — assertion gốc PASS", body, f"submission/notebooks/{name}.ipynb"))
    for name, _, _, _ in items:
        scoped(DEST / "evidence" / f"{name}.html")
        fresh(DEST / "screenshots" / f"{name}.png")
    runtime.mkdir()
    profile = fresh(runtime / "browser")
    temp = fresh(runtime / "temp")
    profile.mkdir()
    temp.mkdir()
    for name, title, body, source in items:
        page = scoped(DEST / "evidence" / f"{name}.html")
        image = scoped(DEST / "screenshots" / f"{name}.png")
        content = ('<!doctype html><html lang="vi"><meta charset="utf-8"><title>' + html.escape(title)
                   + '</title><style>body{margin:32px;background:white;color:#17212b;font:17px Arial}h1{font-size:26px}pre{white-space:pre-wrap;font:15px Consolas;line-height:1.4;padding:20px;background:#f5f8fc;border:1px solid #bdccdb}footer{font-size:14px}</style><h1>'
                   + html.escape(title) + '</h1><p>04/10/2026 — Bằng chứng xuất từ output thật; không phải giao diện Jupyter.</p><pre>'
                   + html.escape(body) + '</pre><footer>Nguồn: ' + html.escape(source) + '</footer></html>')
        if page.exists():
            assert page.read_text(encoding="utf-8") == content, "Preserve existing evidence page"
        else:
            write_new(page, content)
        height = max(950, 250 + len(body.splitlines()) * 23)
        proc = subprocess.run([str(browser), "--headless", "--disable-gpu", "--no-first-run",
                               "--disable-background-networking", "--disable-extensions",
                               f"--user-data-dir={profile}", f"--screenshot={image}",
                               f"--window-size=1400,{height}", "--hide-scrollbars", page.as_uri()],
                              env=dict(os.environ, TEMP=str(temp), TMP=str(temp)),
                              capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        assert proc.returncode == 0 and image.is_file(), proc.stderr[-1000:]
        print(f"{image.name}: {image.stat().st_size} bytes")


if __name__ == "__main__":
    main()
