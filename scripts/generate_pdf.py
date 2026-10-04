"""Compile submission/bonus/ARCHITECTURE.md into submission/bonus/ARCHITECTURE.pdf.
Uses ReportLab with professional typography, headers, tables, and margins.
"""
from __future__ import annotations

import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

MD_PATH = Path("submission/bonus/ARCHITECTURE.md")
PDF_PATH = Path("submission/bonus/ARCHITECTURE.pdf")


def build_pdf():
    print(f"Compiling {MD_PATH} -> {PDF_PATH}...")
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e1e2e"),
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )
    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5,
    )
    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )
    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
    )
    
    story = []
    
    with open(MD_PATH, encoding="utf-8") as f:
        lines = f.readlines()
        
    in_code_block = False
    code_lines = []
    table_lines = []
    in_table = False
    
    for raw_line in lines:
        line = raw_line.rstrip()
        
        # Code block handling
        if line.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "<br/>".join(code_lines)
                p = Paragraph(f"<b>Code/Architecture Schema:</b><br/>{code_text}", code_style)
                story.append(p)
                story.append(Spacer(1, 4))
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            continue
            
        if in_code_block:
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            code_lines.append(safe)
            continue
            
        # Table handling
        if line.startswith("|") and line.endswith("|"):
            if "---" in line:
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            table_lines.append(cols)
            in_table = True
            continue
        elif in_table:
            # Table ended
            in_table = False
            if table_lines:
                table_data = []
                for row_idx, row in enumerate(table_lines):
                    formatted_row = []
                    for col in row:
                        s = Paragraph(col, ParagraphStyle('TC', parent=body_style, fontSize=8, leading=10))
                        formatted_row.append(s)
                    table_data.append(formatted_row)
                    
                t = Table(table_data, hAlign='LEFT')
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ]))
                story.append(t)
                story.append(Spacer(1, 6))
            table_lines = []
            
        # Headers
        if line.startswith("# "):
            story.append(Paragraph(line[2:], title_style))
            story.append(Spacer(1, 4))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], h1_style))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], h2_style))
        elif line.startswith("- ") or line.startswith("* "):
            text = line[2:]
            # formatting
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
            text = re.sub(r"`(.*?)`", r"<font face='Courier'>\1</font>", text)
            story.append(Paragraph(f"• {text}", bullet_style))
        elif line.strip() == "---":
            story.append(Spacer(1, 6))
        elif line.strip():
            text = line.strip()
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
            text = re.sub(r"`(.*?)`", r"<font face='Courier'>\1</font>", text)
            story.append(Paragraph(text, body_style))
        else:
            story.append(Spacer(1, 3))
            
    doc.build(story)
    print(f"  ✓ PDF generated successfully: {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build_pdf()
