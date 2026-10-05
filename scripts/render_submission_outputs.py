"""Render actual saved notebook stdout to PNG; requires Pillow, not Jupyter.

These are labelled output renders, not screenshots of a browser or terminal.
Usage: python scripts/render_submission_outputs.py notebook.ipynb output.png
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont


def render(source: Path, destination: Path) -> None:
    notebook = json.loads(source.read_text(encoding="utf-8"))
    number = source.name[:2]
    blocks = []
    for cell in notebook["cells"]:
        output = "".join("".join(o.get("text", "")) for o in cell.get("outputs", [])
                         if o["output_type"] == "stream" and o["name"] == "stdout")
        if "Bằng chứng rubric" in output:
            blocks.append(output.split("LAB_METRICS_JSON=")[0].rstrip())
        elif number == "01" and "BLOCKED by schema enforcement" in output:
            blocks.append(output)
        elif number == "01" and "First commit JSON" in output:
            blocks.append(output)
        elif number == "03" and "Total versions:" in output:
            blocks.append(output)
        elif number == "04" and "Gold deliverable metrics" in output:
            blocks.append(output)
    if not blocks:
        raise ValueError(f"No executed evidence found in {source}")
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/consola.ttf"
    if not font_path.exists():
        font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
    font = ImageFont.truetype(str(font_path), 19) if font_path.exists() else ImageFont.load_default()
    lines = [f"NB{number} | {source.stem}",
             "OUTPUT RENDER | actual saved notebook stdout | not an app UI screenshot",
             f"Source: submission/notebooks/{source.name}", ""]
    for line in "\n\n".join(blocks).splitlines():
        lines.extend(textwrap.wrap(line, width=150, replace_whitespace=False, drop_whitespace=False,
                                   subsequent_indent="    ") or [""])
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    width = max(1000, int(max(probe.textlength(line, font=font) for line in lines)) + 64)
    canvas = Image.new("RGB", (width, 32 + len(lines) * 28), "#f7f9fc")
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        draw.text((32, 16 + index * 28), line, font=font, fill="#193047")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
