"""Render captured notebook outputs in a local page and take real screenshots."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
import subprocess
import sys

import nbformat

from execute_submission_safe import DATA, DEST, REPO, inside


def main():
    render_only = "--html-only" in sys.argv
    browser = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    assert browser.is_file()
    profile = inside(DATA / "evidence_browser_capture3")
    if profile.exists() and not render_only:
        raise RuntimeError("Existing browser artifacts must be preserved")
    if not render_only:
        profile.mkdir()
    temp = inside(DATA / "evidence_temp_capture3")
    if not render_only:
        temp.mkdir()
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp))
    shots = inside(DEST / "screenshots")
    pages = inside(DEST / "evidence")
    shots.mkdir(parents=True, exist_ok=True)
    pages.mkdir(parents=True, exist_ok=True)
    for notebook in sorted((DEST / "notebooks").glob("*.ipynb")):
        nb = nbformat.read(notebook, as_version=4)
        texts = []
        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            out = "".join(o.get("text", "") for o in cell.outputs if o.output_type == "stream")
            if not out:
                continue
            code = cell.source
            number = notebook.name[:2]
            if number == "02" and "for mn, mx in sorted(ranges)" in code:
                out = out[out.index("──── Z-order deliverable metrics"):]
            if number == "05" and ("waste_tb" in code or "snapshot[0]" in code):
                continue
            if number == "07" and ("brute-force" in code or "100_000" in code or "No sync job" in code):
                continue
            if number == "08" and ("json.dumps(training_run" in code or "mcp.meter" in code or "json.dumps(model_card" in code):
                continue
            texts.append(out.strip())
        status = nb.metadata["lab_execution_status"]
        body = "\n\n".join(texts)
        if notebook.name.startswith("01"):
            logdir = inside(DATA / "scratch" / "users_delta" / "_delta_log")
            commits = sorted(p.name for p in logdir.glob("*.json"))
            first = logdir / commits[0]
            entries = [json.loads(line) for line in first.read_text(encoding="utf-8").splitlines()]
            body += "\n\n_delta_log/: " + ", ".join(commits)
            body += "\nCommit v0 — metadata và add thực tế:\n" + json.dumps([e for e in entries if "metaData" in e or "add" in e], ensure_ascii=False, indent=2)
        if status != "complete":
            body += "\n\nCHƯA HOÀN TẤT: các bước phá hủy và các cell phụ thuộc chưa thực thi."
        page = inside(pages / f"{notebook.stem}.html")
        shot = inside(shots / f"nb{notebook.name[:2]}_{notebook.stem[3:]}.png")
        assert not shot.exists()
        content = '<!doctype html><html lang="vi"><meta charset="utf-8"><title>' + html.escape(notebook.stem) + '</title><style>body{margin:30px;background:#fff;color:#17212b;font:16px Arial}h1{font-size:25px;margin-bottom:8px}.status{font-weight:bold;color:#244d72}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px Consolas,monospace;line-height:1.32;padding:18px;border:1px solid #ccd5df;background:#f8fafc}footer{font-size:13px;color:#536171}</style><h1>' + html.escape(notebook.stem) + '</h1><p class="status">Trạng thái: ' + status + '</p><p>Output thật trích từ notebook đã thực thi trên máy. Trang bằng chứng xuất từ ipynb; không phải giao diện Jupyter.</p><pre>' + html.escape(body) + '</pre><footer>Nguồn: submission/notebooks/' + html.escape(notebook.name) + '</footer></html>'
        if page.exists():
            assert page.read_text(encoding="utf-8") == content, "Preserve existing evidence page"
        else:
            with page.open("x", encoding="utf-8") as f:
                f.write(content)
        if render_only:
            print(f"Evidence HTML: {page.name}", flush=True)
            continue
        height = min(12000, max(1600, 250 + len(body.splitlines()) * 20))
        result = subprocess.run([str(browser), "--headless", "--disable-gpu", "--no-first-run", "--disable-background-networking", "--disable-extensions", f"--user-data-dir={profile}", f"--screenshot={shot}", f"--window-size=1400,{height}", "--hide-scrollbars", page.as_uri()], env=env, capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or not shot.exists():
            raise RuntimeError(result.stderr.decode(errors="replace")[-1500:])
        print(f"Screenshot: {shot.name} ({shot.stat().st_size:,} bytes)", flush=True)


if __name__ == "__main__":
    main()
