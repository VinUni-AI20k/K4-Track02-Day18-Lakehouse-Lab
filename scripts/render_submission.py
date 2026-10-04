"""Render original executed notebook output as screenshots and a six-page brief."""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def render_evidence():
    import nbformat
    from nbconvert import HTMLExporter
    from playwright.sync_api import sync_playwright

    selectors = {
        "01": ("BLOCKED", "Transaction log files:", "premium"),
        "02": ("Files before", "Files after", "Z-order deliverable", "file", "Speedup"),
        "03": ("MERGE 100K", "Rows with score", "Total versions", "v0 row count"),
        "04": ("Bronze rows:", "Silver rows:", "Gold deliverable", "shape: (21", "[PASS]"),
        "05": ("Catalog:", "Partition spec:", "Pruning ratio", "Tier 1", "metadata is", "Field IDs", "specs in use", "[PASS]"),
        "06": ("BASELINE", "File reduction", "skip rate", "Reclaimed:", "Orphans found:", "Checkpoint written:", "snapshots:", "Stranded manifest", "[PASS]"),
        "07": ("amplification:", "On disk", "recall@10", "Erased docs", "CDF rows", "[PASS]", "Query doc:"),
        "08": ("Bronze trajectory", "Silver:", "Matches what training", "Actual catalog", "resultType:", "tasks/get", "Partitions on disk:", "UNCLASSIFIED rows:", "Rows for", "[PASS]", "shape: (2"),
    }
    metrics = json.loads((OUT / "evidence" / "metrics.json").read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", headless=True)
        page = browser.new_page(viewport={"width": 2200, "height": 1200}, device_scale_factor=1)
        for ipynb in sorted((OUT / "notebooks").glob("*.ipynb")):
            nb = nbformat.read(ipynb, as_version=4)
            key = ipynb.name[:2]
            outputs = []
            for cell in nb.cells:
                text = "".join(o.get("text", "") for o in cell.get("outputs", []))
                if text.startswith("MEASURED_JSON="):
                    continue
                if text and any(s in text for s in selectors[key]):
                    outputs.append(text)
            assert outputs, ipynb
            content = "\n\n".join(outputs)
            body = f"""<!doctype html><meta charset='utf-8'><style>
            body{{margin:48px;background:#f4f7fa;color:#14293b;font-family:Arial}}
            h1{{font-size:32px}} p{{font-size:20px}}
            pre{{background:white;border:1px solid #ccd8e0;border-radius:10px;padding:24px;
            font:17px/1.4 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}
            </style><h1>{html.escape(ipynb.stem)}</h1>
            <p>Đỗ Quốc An · 2A202602892 · Lightweight Python 3.11 · Executed Jupyter output</p>
            <p>Run: {html.escape(metrics['executed_at'])} | Source: submission/notebooks/{ipynb.name}</p>
            <pre>{html.escape(content)}</pre>"""
            evidence = OUT / "evidence" / f"{ipynb.stem}.html"
            evidence.write_text(body, encoding="utf-8")
            page.goto(evidence.as_uri())
            page.screenshot(path=str(OUT / "screenshots" / f"nb{key}_{ipynb.stem[3:]}.png"), full_page=True)
            full, _ = HTMLExporter().from_notebook_node(nb)
            (OUT / "evidence" / f"{ipynb.stem}_full.html").write_text(full, encoding="utf-8")
            print("Screenshot:", ipynb.stem, flush=True)
        browser.close()


def render_brief():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Preformatted, Spacer, PageBreak
    import fitz

    pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
    pdfmetrics.registerFont(TTFont("ArialBold", r"C:\Windows\Fonts\arialbd.ttf"))
    pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="ArialBold", italic="Arial", boldItalic="ArialBold")
    styles = {
        "body": ParagraphStyle("body", fontName="Arial", fontSize=10, leading=14, spaceAfter=9, textColor=colors.HexColor("#183044")),
        "h1": ParagraphStyle("h1", fontName="ArialBold", fontSize=21, leading=26, spaceAfter=14, textColor=colors.HexColor("#123c55")),
        "h2": ParagraphStyle("h2", fontName="ArialBold", fontSize=15, leading=20, spaceAfter=12, textColor=colors.HexColor("#123c55")),
        "code": ParagraphStyle("code", fontName="Arial", fontSize=8.3, leading=11),
    }
    source = (OUT / "bonus" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    # Explicit section boundaries produce the requested 3-6-page brief.
    blocks = re.split(r"\n\s*\n", source)
    story = []
    for block in blocks:
        block = block.replace("→", "->").replace("—", "-").replace("–", "-").replace("≤", "<=").replace("≥", ">=")
        if block.startswith(("## 3.", "## 4.", "## 5.", "## 6.")):
            story.append(PageBreak())
        if "```" in block:
            story.append(Preformatted(block.strip("`\n").removeprefix("text\n"), styles["code"]))
            story.append(Spacer(1, 10))
            continue
        if block.startswith("# "):
            role, block = "h1", block[2:]
        elif block.startswith("## "):
            role, block = "h2", block[3:]
        else:
            role = "body"
        text = html.escape(block)
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" color="#13678a">\1</a>', text)
        text = text.replace("\n- ", "<br/>• ").removeprefix("- ")
        story.append(Paragraph(text, styles[role]))
    pdf = OUT / "bonus" / "ARCHITECTURE.pdf"
    def footer(canvas, doc):
        canvas.setFont("Arial", 8)
        canvas.setFillColor(colors.HexColor("#526575"))
        canvas.drawString(42, 26, "K4-Track02-Day18 | Đỗ Quốc An | 2A202602892 | Architecture brief")
        canvas.drawRightString(A4[0]-42, 26, str(doc.page))
    SimpleDocTemplate(str(pdf), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=38, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)
    document = fitz.open(pdf)
    print("PDF pages:", len(document), flush=True)
    assert 3 <= len(document) <= 6, "Architecture brief must be 3-6 pages"
    qa = ROOT / "tmp" / "pdfs"
    qa.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(document):
        page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4)).save(qa / f"architecture-{i+1}.png")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    render_evidence()
    render_brief()
