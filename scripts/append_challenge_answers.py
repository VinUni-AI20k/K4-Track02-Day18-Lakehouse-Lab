"""Add challenge-specific explanations, preserving executed output."""
import nbformat
from execute_submission_safe import DEST, inside

document = (DEST / "EXPLANATIONS.md").read_text(encoding="utf-8")
sections = document.split("\n## ")[1:9]
assert len(sections) == 8
for i, notebook in enumerate(sorted((DEST / "notebooks").glob("*.ipynb"))):
    target = inside(notebook)
    nb = nbformat.read(target, as_version=4)
    marker = "### Trả lời câu hỏi thử thách"
    assert not any(c.cell_type == "markdown" and c.source.startswith(marker) for c in nb.cells)
    text = marker + "\n\n" + sections[i]
    nb.cells.append(nbformat.v4.new_markdown_cell(text))
    nbformat.validate(nb)
    nbformat.write(nb, target)
    print(notebook.name)
