"""Capture real notebook outputs; stop before destructive lab operations.

Run once from a fresh _lakehouse. Existing data is never reset or cleaned.
Uses IPython execution and nbformat outputs, without an external kernel.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "_lakehouse"
DEST = REPO / "submission"


def inside(p):
    p = Path(p).resolve()
    if not p.is_relative_to(REPO) or p == REPO:
        raise RuntimeError(f"Outside authorized scope: {p}")
    return p


def guards():
    sys.path.insert(0, str(REPO / "notebooks"))
    import lakehouse

    def fresh_only(*targets):
        for target in targets:
            p = inside(target)
            if p.exists():
                raise RuntimeError(f"Preserving existing data; reset refused: {p}")

    def fresh_catalog(name="lab"):
        fresh_only(lakehouse._catalog_dir(name))

    lakehouse.reset = fresh_only
    lakehouse.reset_catalog = fresh_catalog


def execute(name):
    inside(DATA / "runtime" / "ipython").mkdir(parents=True, exist_ok=True)
    os.environ["IPYTHONDIR"] = str(DATA / "runtime" / "ipython")
    import jupytext
    import nbformat
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output

    guards()
    source = inside(REPO / "notebooks" / f"{name}.py")
    target = inside(DEST / "notebooks" / f"{name}.ipynb")
    if target.exists():
        raise RuntimeError(f"Preserving previous output: {target}")
    nb = jupytext.read(source)
    nb.metadata.pop("jupytext", None)
    nb.metadata.kernelspec = {"display_name": "Python (lab .venv)", "language": "python", "name": "python3"}
    nb.metadata.language_info = {"name": "python", "version": sys.version.split()[0]}
    note = "Chạy thực tế trên máy bằng IPython trong `.venv`. Reset chỉ được phép khi đích chưa tồn tại; không xóa dữ liệu. Assertion và ngưỡng gốc được giữ nguyên."
    nb.cells.insert(1, nbformat.v4.new_markdown_cell(note))
    shell = InteractiveShell.instance()
    status = "complete"
    count = 0
    for index, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        code = cell.source
        marker = None
        if name.startswith("06_") and "dry_run=False" in code:
            marker = "dt.vacuum(retention_hours=0, dry_run=False"
        if name.startswith(("07_", "08_")) and "dt.delete(" in code:
            marker = "dt.delete("
        prefix = code[:code.index(marker)] if marker else code
        count += 1
        cell.execution_count = count
        print(f"{name}: cell {index} ({count})", flush=True)
        with capture_output() as captured:
            result = shell.run_cell(prefix, store_history=False)
        outputs = []
        if captured.stdout:
            outputs.append(nbformat.v4.new_output("stream", name="stdout", text=captured.stdout))
        if captured.stderr:
            outputs.append(nbformat.v4.new_output("stream", name="stderr", text=captured.stderr))
        for rich in captured.outputs:
            outputs.append(nbformat.v4.new_output("display_data", data=rich.data, metadata=rich.metadata))
        error = result.error_before_exec or result.error_in_exec
        if error:
            outputs.append(nbformat.v4.new_output("error", ename=type(error).__name__, evalue=str(error), traceback=traceback.format_exception(error)))
            status = "error"
        cell.outputs = outputs
        if marker:
            # Retain original unexecuted destructive code in its own cell.
            cell.source = prefix
            nb.cells.insert(index + 1, nbformat.v4.new_markdown_cell("**DỪNG THEO CHÍNH SÁCH BẢO TOÀN DỮ LIỆU:** chưa thực thi cell phá hủy bên dưới và các cell tiếp theo. Không báo PASS cho notebook này."))
            nb.cells.insert(index + 2, nbformat.v4.new_code_cell(code[len(prefix):]))
            status = "pending_authorization"
        if error or marker:
            break
    nb.metadata["lab_execution_status"] = status
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        nbformat.write(nb, handle)
    summary = {"notebook": name, "status": status, "code_cells_executed": count}
    log = inside(DEST / "logs" / f"{name}.json")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary), flush=True)
    return 1 if status == "error" else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook")
    args = parser.parse_args()
    if args.notebook:
        return execute(args.notebook)
    if DATA.exists() or DEST.exists():
        raise RuntimeError("Fresh run required; existing _lakehouse/submission preserved.")
    os.environ["LAKEHOUSE_ROOT"] = str(DATA)
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["IPYTHONDIR"] = str(DATA / "runtime" / "ipython")
    guards()
    import generate_data_lite
    import generate_ai_data
    generate_data_lite.main()
    generate_ai_data.main()
    for source in sorted((REPO / "notebooks").glob("[0-9]*.py")):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--notebook", source.stem], cwd=REPO, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
