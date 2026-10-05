"""Render the six source sections to PDF and PNGs for visual inspection."""
import html
import re
from pathlib import Path

import pymupdf
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted, Table, TableStyle

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
FONTDIR = Path("C:/Windows/Fonts")
FONT_FILES = {"Lab": "arial.ttf", "Lab-Bold": "arialbd.ttf", "Lab-Italic": "ariali.ttf", "Mono": "consola.ttf"}
for name, filename in FONT_FILES.items():
    if not (FONTDIR / filename).exists():
        raise SystemExit("This renderer uses Arial/Consolas on Windows; see README for font portability.")
    pdfmetrics.registerFont(TTFont(name, str(FONTDIR / filename)))
pdfmetrics.registerFontFamily("Lab", normal="Lab", bold="Lab-Bold", italic="Lab-Italic", boldItalic="Lab-Bold")
NAVY = colors.HexColor("#143149")
TEAL = colors.HexColor("#006b72")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyVN", fontName="Lab", fontSize=9.1, leading=12.1,
                          spaceAfter=6, textColor=colors.HexColor("#223444")))
styles.add(ParagraphStyle(name="TitleVN", fontName="Lab-Bold", fontSize=20, leading=25,
                          textColor=NAVY, spaceAfter=12))
styles.add(ParagraphStyle(name="H2VN", fontName="Lab-Bold", fontSize=14, leading=18,
                          spaceBefore=6, spaceAfter=10, textColor=NAVY, keepWithNext=True))
styles.add(ParagraphStyle(name="H3VN", fontName="Lab-Bold", fontSize=10.5, leading=14,
                          spaceBefore=7, spaceAfter=6, textColor=TEAL, keepWithNext=True))
styles.add(ParagraphStyle(name="CellVN", fontName="Lab", fontSize=8.1, leading=10.4, spaceAfter=0))
styles.add(ParagraphStyle(name="DiagramVN", fontName="Mono", fontSize=8, leading=10.7,
                          backColor=colors.HexColor("#eef4f7"), borderPadding=10,
                          spaceBefore=5, spaceAfter=10))


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: '<link href="' + m[2] + '" color="#006b72">' + m[1] + '</link>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r'<font name="Mono">\1</font>', s)
    return s


def footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(colors.HexColor("#b8cbd5"))
    canvas.line(38, h - 29, w - 38, h - 29)
    canvas.setFont("Lab", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(38, h - 22, "K4 / Day18    BONUS A    |    Architecture review")
    canvas.drawString(38, 24, "Hoàng Thái Đạt   |   2A202602959   |   Local draft - 05/10/2026")
    canvas.drawRightString(w - 38, 24, f"{doc.page} / 6")
    canvas.restoreState()


lines = (BASE / "ARCHITECTURE.md").read_text(encoding="utf-8").splitlines()
flow, i = [], 0
while i < len(lines):
    line = lines[i]
    if not line.strip():
        i += 1
        continue
    if line == "<!-- pagebreak -->":
        flow.append(PageBreak())
        i += 1
    elif line.startswith("```"):
        i += 1
        code = []
        while i < len(lines) and not lines[i].startswith("```"):
            code.append(lines[i])
            i += 1
        flow.append(Preformatted("\n".join(code), styles["DiagramVN"]))
        i += 1
    elif line.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            parts = [s.strip() for s in lines[i].strip("|").split("|")]
            if not all(re.fullmatch(r":?-+:?", p) for p in parts):
                rows.append(parts)
            i += 1
        width = A4[0] - 76
        widths = [width * x for x in ([.16, .84] if len(rows[0]) == 2 else [.26, .58, .16])]
        data = [[Paragraph(inline(c), styles["CellVN"]) for c in row] for row in rows]
        table = Table(data, colWidths=widths, repeatRows=1, hAlign=TA_LEFT)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcebf0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#9eb5c2")),
        ]))
        flow.extend([table, Spacer(1, 7)])
    elif line.startswith("#"):
        level = len(line) - len(line.lstrip("#"))
        flow.append(Paragraph(inline(line[level:].strip()), styles[{1: "TitleVN", 2: "H2VN"}.get(level, "H3VN")]))
        i += 1
    else:
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "```", "<!--")):
            paragraph.append(lines[i])
            i += 1
        flow.append(Paragraph(inline(" ".join(paragraph)), styles["BodyVN"]))
target = BASE / "ARCHITECTURE.pdf"
doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=38, leftMargin=38,
                         topMargin=43, bottomMargin=42,
                         title="Bonus A - LLM observability lakehouse", author="Hoàng Thái Đạt")
doc.build(flow, onFirstPage=footer, onLaterPages=footer)
count = len(PdfReader(target).pages)
print(f"Rendered {count} pages")
assert count == 6, f"Expected 6 source sections on 6 pages, got {count}; inspect layout and adjust."
out = REPO / "tmp/pdfs/bonus"
out.mkdir(parents=True, exist_ok=True)
with pymupdf.open(target) as pdf:
    for n, page in enumerate(pdf, 1):
        page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6)).save(str(out / f"page-{n}.png"))
        blocks = page.get_text("blocks")
        assert all(b[0] >= 25 and b[2] <= A4[0] - 25 for b in blocks), f"Horizontal overflow page {n}"
print(f"Rendered QA images: {out}")
