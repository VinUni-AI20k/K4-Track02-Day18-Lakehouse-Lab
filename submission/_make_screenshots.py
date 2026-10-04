"""Render key notebook outputs to terminal-style PNG screenshots for submission.

Not part of the lab runtime; a submission helper. Run from the repo root:

    ./.venv/Scripts/python.exe submission/_make_screenshots.py
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"
OUT = ROOT / "submission" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

MONO = "C:/Windows/Fonts/consola.ttf"
MONO_B = "C:/Windows/Fonts/consolab.ttf"
FONT = ImageFont.truetype(MONO, 18)
FONT_B = ImageFont.truetype(MONO_B, 18)

BG = (13, 17, 23)
FG = (201, 209, 217)
GREEN = (63, 185, 80)
DIM = (139, 148, 158)
BAR = (30, 36, 44)
TITLE_FG = (230, 237, 243)


def cell_stream_text(nb_path: Path) -> list[str]:
    d = json.loads(nb_path.read_text(encoding="utf-8"))
    lines: list[str] = []
    for c in d["cells"]:
        if c.get("cell_type") != "code":
            continue
        for o in c.get("outputs", []):
            if o.get("output_type") == "stream":
                lines.extend("".join(o["text"]).rstrip("\n").split("\n"))
            elif o.get("output_type") == "execute_result":
                data = o.get("data", {})
                if "text/plain" in data:
                    txt = "".join(data["text/plain"])
                    lines.extend(txt.rstrip("\n").split("\n"))
    return lines


def wrap(lines: list[str], width: int = 118) -> list[str]:
    out: list[str] = []
    for ln in lines:
        if len(ln) <= width:
            out.append(ln)
        else:
            out.extend(textwrap.wrap(ln, width) or [""])
    return out


def render(title: str, body: list[str], path: Path, max_lines: int = 60) -> None:
    body = wrap(body)[:max_lines]
    pad, line_h = 24, 24
    header_h = 46
    # measure widest line
    tmp = Image.new("RGB", (10, 10))
    td = ImageDraw.Draw(tmp)
    w = max((td.textlength(l, font=FONT) for l in body), default=800)
    w = max(w, td.textlength(title, font=FONT_B))
    width = int(min(max(w + pad * 2, 900), 1900))
    height = header_h + pad + line_h * len(body) + pad
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    # title bar
    d.rectangle([0, 0, width, header_h], fill=BAR)
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 20 + i * 22
        d.ellipse([cx - 7, header_h // 2 - 7, cx + 7, header_h // 2 + 7], fill=col)
    d.text((92, header_h // 2 - 10), title, font=FONT_B, fill=TITLE_FG)
    y = header_h + pad
    for ln in body:
        color = FG
        if "[PASS]" in ln or "✓" in ln:
            color = GREEN
        elif "[FAIL]" in ln or "VIOLATION" in ln:
            color = (248, 81, 73)
        elif ln.strip().startswith("#") or ln.startswith("────"):
            color = DIM
        d.text((pad, y), ln, font=FONT, fill=color)
        y += line_h
    img.save(path)
    print(f"wrote {path.relative_to(ROOT)}  ({width}x{height})")


def banner(title: str, sub: str = "") -> list[str]:
    return ["", f"  ── {title} ──", (f"  {sub}" if sub else ""), ""]


# ── NB1: transaction log + commit JSON + enforcement ──────────────────────
def nb01() -> None:
    table = ROOT / "_lakehouse" / "scratch" / "users_delta"
    log = sorted((table / "_delta_log").glob("*.json"))
    body = banner("NB1 — Delta transaction log")
    body.append(f"  _delta_log/ directory: {table / '_delta_log'}")
    body.append("")
    for f in log:
        body.append(f"    {f.name}   ({f.stat().st_size} bytes)")
    body.append("")
    body.append(f"  commit JSON files: {len(log)}   (>= 2 required)")
    body.append("")
    body.append("  ── contents of the final commit JSON (truncated) ──")
    body.append("")
    last = log[-1].read_text(encoding="utf-8")
    for ln in last.splitlines()[:6]:
        body.append("    " + ln[:150])
    render("NB1 · _delta_log evidence", body, OUT / "nb01_delta_log.png")

    body = cell_stream_text(NB / "01_delta_basics.ipynb")
    render("NB1 · schema enforcement + evolution + DuckDB", body,
           OUT / "nb01_schema_enforcement.png")


# ── NB2 ───────────────────────────────────────────────────────────────────
def nb02() -> None:
    lines = cell_stream_text(NB / "02_optimize_zorder.ipynb")
    keep = [l for l in lines if "file user_id range" not in l]
    render("NB2 · OPTIMIZE + Z-ORDER (files 200→55, speedup 9.8×, prune 55×)",
           keep, OUT / "nb02_optimize.png")


# ── NB3 ───────────────────────────────────────────────────────────────────
def nb03() -> None:
    render("NB3 · time travel + MERGE 100K + RESTORE (5 versions)",
           cell_stream_text(NB / "03_time_travel.ipynb"), OUT / "nb03_time_travel.png")


# ── NB4 ───────────────────────────────────────────────────────────────────
def nb04() -> None:
    lines = cell_stream_text(NB / "04_medallion.ipynb")
    keep = [l for l in lines if not l.startswith("│") and not l.startswith("╞")
            and not l.startswith("└") and not l.startswith("┌")
            and not l.startswith("├") and not l.startswith("…")]
    keep = [l for l in keep if l.strip() != ""] or lines
    render("NB4 · Bronze→Silver→Gold (200K→190,052; Gold 24 rows = 8 dates × 3 models)",
           keep, OUT / "nb04_medallion.png")


# ── NB5 ───────────────────────────────────────────────────────────────────
def nb05() -> None:
    render("NB5 · Iceberg catalog: pruning 10×, field_id=4 stable, 2 specs",
           cell_stream_text(NB / "05_iceberg_catalog.ipynb"), OUT / "nb05_iceberg.png")


# ── NB6 ───────────────────────────────────────────────────────────────────
def nb06() -> None:
    render("NB6 · maintenance: 5 jobs (compaction 18×, skip 90%, orphans, checkpoint)",
           cell_stream_text(NB / "06_maintenance.ipynb"), OUT / "nb06_maintenance.png")


# ── NB7 ───────────────────────────────────────────────────────────────────
def nb07() -> None:
    render("NB7 · multimodal + vectors: amplification 200×, int8 5.8×, lifecycle bug",
           cell_stream_text(NB / "07_vectors_multimodal.ipynb"), OUT / "nb07_vectors.png")


# ── NB8 ───────────────────────────────────────────────────────────────────
def nb08() -> None:
    lines = cell_stream_text(NB / "08_agents_provenance.ipynb")
    keep = [l for l in lines if not l.startswith("│") and not l.startswith("╞")
            and not l.startswith("└") and not l.startswith("┌")
            and not l.startswith("├") and not l.startswith("…")]
    keep = [l for l in keep if l.strip() != ""] or lines
    render("NB8 · agents + provenance: version pin, MCP sim, 4 buckets",
           keep, OUT / "nb08_agents.png")


if __name__ == "__main__":
    nb01(); nb02(); nb03(); nb04(); nb05(); nb06(); nb07(); nb08()
    print("\nAll screenshots written.")
