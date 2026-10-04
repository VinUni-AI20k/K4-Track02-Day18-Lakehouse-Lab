"""Emit targeted notebook edits and real read-only NB6 output; no file writes."""
import contextlib
import difflib
import io
from pathlib import Path

import nbformat

REPO = Path(__file__).resolve().parents[1]


def main():
    patches = []
    for number, name in [(6, "06_maintenance"), (7, "07_vectors_multimodal"), (8, "08_agents_provenance")]:
        target = REPO / "submission" / "notebooks" / f"{name}.ipynb"
        original = target.read_text(encoding="utf-8")
        nb = nbformat.reads(original, as_version=4)
        if number == 6:
            for cell in nb.cells:
                if cell.cell_type == "code" and cell.execution_count is None and "def find_orphans(" in cell.source:
                    cell.source = cell.source.replace(
                        '    referenced = {os.path.realpath(u.replace("file://", ""))',
                        '    from urllib.parse import unquote\n    referenced = {os.path.realpath(unquote(u.replace("file://", "")))')
            nb.cells.append(nbformat.v4.new_markdown_cell(
                "### Cập nhật thực tế ngày 04/10/2026 — NB6 chưa hoàn tất\n\n"
                "Đã tạo/tìm 3 orphan và baseline Iceberg 20 snapshots/2.000 hàng. Chưa chạy VACUUM, expiry hoặc sweep. "
                "Source đã sửa byte VACUUM và URI có dấu cách; output cũ được giữ nguyên. Cell chỉ đọc dưới đây "
                "đo lại byte ứng viên và hàng hiện tại; đây không phải byte thu hồi. Checkpoint tự động ở v99/v199 đã có. "
                "Danh sách đích: `submission/REVIEW_20261004.json`."))
            code = '''from pathlib import Path
from deltalake import DeltaTable
import json
repo = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "submission/logs/preparation_20261004.json").is_file())
table = repo / "_lakehouse/scratch/maint_events"
delta = DeltaTable(str(table))
candidates = delta.vacuum(retention_hours=0, dry_run=True, enforce_retention_duration=False)
paths = [Path(f) if Path(f).is_absolute() else table / f for f in candidates]
print(f"VACUUM dry-run: {len(paths)} files / {sum(p.stat().st_size for p in paths):,} bytes")
print(f"Current rows unchanged: {delta.count():,}")
prep = json.loads((repo / "submission/logs/preparation_20261004.json").read_text(encoding="utf-8"))
print(f"Prepared: {prep['planted_orphans']} orphans / {prep['planted_orphan_bytes']:,} bytes; Iceberg {prep['iceberg_snapshots']} snapshots / {prep['iceberg_rows']:,} rows")
print("VACUUM/expiry/sweep not executed; NB6 remains incomplete.")
'''
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(code, {})
            cell = nbformat.v4.new_code_cell(code)
            cell.execution_count = max(c.execution_count or 0 for c in nb.cells if c.cell_type == "code") + 1
            cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text=output.getvalue())]
            nb.cells.append(cell)
        else:
            text = (
                "NB7: user_042 có **0 hits in-table, 8 hits external**, CDF phát đúng **8 delete events**. "
                "**7 assertion gốc PASS**. Current còn 1.992 hàng; v0 vẫn đọc đủ 2.000 hàng. External index "
                "vẫn chứa 8 doc_id đã xóa trong current table, nên đã tái hiện stale-index bug. Chưa VACUUM hoặc đồng bộ index."
                if number == 7 else
                "NB8: user_007 có **8 → 0 hàng**, table **v0 → v1**; **10 assertion gốc PASS**. Bảng v0 vẫn đọc đủ "
                "2.000 hàng và chứa 8 hàng subject. Kết quả chứng minh xóa trong current version, không phải xóa "
                "file/version cũ hay chứng nhận erasure toàn hệ thống.")
            nb.cells.append(nbformat.v4.new_markdown_cell(
                "### Giải thích kết quả cuối sau xác nhận ngày 04/10/2026\n\n" + text
                + "\n\nCác đoạn ‘chưa xóa/chưa CDF’ phía trên mô tả lần chạy ban đầu; kết quả mới và assertion đã chạy "
                "nằm trong các cell tiếp tục. Kiểm tra độc lập: `submission/logs/row_deletions_20261004.json`."))
        nbformat.validate(nb)
        revised = nbformat.writes(nb)
        diff = list(difflib.unified_diff(original.splitlines(), revised.splitlines(), n=3))[2:]
        diff = ["@@" if line.startswith("@@") else line for line in diff]
        patches.append("*** Update File: " + str(target) + "\n" + "\n".join(diff) + "\n")
    print("*** Begin Patch\n" + "".join(patches) + "*** End Patch")


if __name__ == "__main__":
    main()
