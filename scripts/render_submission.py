"""Render actual notebook evidence with headless Chrome and the brief with ReportLab.

Artifact environment: uv pip install reportlab pymupdf
Chrome uses a separate temporary profile, not the user's browser session.
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def screenshots():
    candidates = [shutil.which("google-chrome"), shutil.which("chromium"),
                  "C:/Program Files/Google/Chrome/Application/chrome.exe",
                  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"]
    chrome = next((p for p in candidates if p and Path(p).is_file()), None)
    if not chrome:
        raise RuntimeError("Chrome or Chromium is required to capture evidence pages")
    (OUT / "screenshots").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lakehouse-evidence-") as profile:
        for page in sorted((OUT / "evidence").glob("[0-9]*.html")):
            # Each preformatted row needs 21px; allow wrapped paths/JSON and header.
            content = page.read_text(encoding="utf-8")
            pre = html.unescape(content.split("<pre>")[1].split("</pre>")[0])
            rows = sum(max(1, (len(line) + 135) // 136) for line in pre.splitlines())
            height = max(900, 260 + rows * 22)
            target = OUT / "screenshots" / ("nb" + page.stem + ".png")
            subprocess.run([chrome, "--headless", "--disable-gpu", "--no-first-run",
                            "--no-default-browser-check", "--hide-scrollbars",
                            "--allow-file-access-from-files", f"--user-data-dir={profile}",
                            f"--window-size=1440,{height}", f"--screenshot={target}", page.as_uri()],
                           check=True, capture_output=True, timeout=60,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            assert target.is_file() and target.stat().st_size > 1000
            print(f"Screenshot: {target.name}")


def bonus_pdf():
    import pymupdf
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted

    font_root = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("Lab", str(font_root / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("LabBold", str(font_root / "arialbd.ttf")))
    pdfmetrics.registerFontFamily("Lab", normal="Lab", bold="LabBold", italic="Lab", boldItalic="LabBold")
    styles = {
        "body": ParagraphStyle("body", fontName="Lab", fontSize=9.2, leading=13.1, spaceAfter=6.2,
                               alignment=TA_LEFT, textColor=colors.HexColor("#233747")),
        "h1": ParagraphStyle("h1", fontName="LabBold", fontSize=20, leading=25, spaceAfter=13),
        "h2": ParagraphStyle("h2", fontName="LabBold", fontSize=13, leading=17, spaceBefore=7, spaceAfter=9),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=7.7, leading=10.4, spaceAfter=10),
    }

    def inline(text):
        text = html.escape(text)
        text = re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)", r'<a href="\2" color="#126077">\1</a>', text)
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"`([^`]+)`", r"<b>\1</b>", text)
        return text

    story = []
    source = (OUT / "bonus" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    pages = source.split("<!-- pagebreak -->")
    for i, page in enumerate(pages):
        if i:
            story.append(PageBreak())
        for block in page.strip().split("\n\n"):
            if block.startswith("```"):
                story.append(Preformatted(block.strip().removeprefix("```text\n").removesuffix("```"), styles["code"]))
            elif block.startswith("# "):
                story.append(Paragraph(inline(block[2:]), styles["h1"]))
            elif block.startswith("## "):
                story.append(Paragraph(inline(block[3:]), styles["h2"]))
            elif block.startswith("- "):
                for item in re.split(r"\n- ", block[2:]):
                    story.append(Paragraph("• " + inline(" ".join(item.splitlines())), styles["body"]))
            else:
                story.append(Paragraph(inline(" ".join(block.splitlines())), styles["body"]))
    target = OUT / "bonus" / "ARCHITECTURE.pdf"

    def footer(canvas, doc):
        canvas.setFont("Lab", 8)
        canvas.setFillColor(colors.HexColor("#586c7c"))
        canvas.drawString(40, 25, "Trần Đại Nhân | 2A202602642 | Lakehouse Architecture Brief")
        canvas.drawRightString(A4[0] - 40, 25, str(doc.page))

    SimpleDocTemplate(str(target), pagesize=A4, rightMargin=40, leftMargin=40,
                      topMargin=35, bottomMargin=42, title="LLM observability: 1 tỷ request/ngày",
                      author="Trần Đại Nhân").build(story, onFirstPage=footer, onLaterPages=footer)
    doc = pymupdf.open(target)
    assert 3 <= len(doc) <= 6, f"Bonus must be 3-6 pages; rendered {len(doc)}"
    preview = ROOT / "_lakehouse" / "artifact-preview"
    preview.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(doc):
        page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(preview / f"bonus-{i + 1}.png")
    print(f"Bonus rendered: {len(doc)} pages. Preview: {preview}")


if __name__ == "__main__":
    screenshots()
    bonus_pdf()
