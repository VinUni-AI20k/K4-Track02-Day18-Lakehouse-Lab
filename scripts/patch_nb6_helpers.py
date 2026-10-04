"""Emit a notebook patch defining the bounded resume helpers for review.

Only execute function definitions, never the maintenance actions again.
"""
import difflib
from pathlib import Path

import nbformat

REPO = Path(__file__).resolve().parents[1]

HELPERS = '''# Definitions for the bounded resume callbacks; do not rerun completed actions.
import hashlib
def checked_nb6_path(value):
    p = Path(value).resolve()
    workspace = Path(review["workspace"]).resolve()
    assert p.is_relative_to(workspace / "_lakehouse")
    assert p != workspace / "_lakehouse"
    return p
def checked_nb6_record(value, records):
    p = checked_nb6_path(value)
    record = next(r for r in records if checked_nb6_path(r["path"]) == p)
    assert p.is_file() and p.stat().st_size == record["bytes"]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == record["sha256"]
    return p
def vacuum_reviewed():
    assert hashlib.sha256((ROOT.parent / "submission/REVIEW_20261004.json").read_bytes()).hexdigest() == "5f3353489c9260560459fe5dea33154702026336138dc7328f40d0fcd774cd7b"
    t = DeltaTable(TABLE)
    assert t.version() == review["vacuum"]["version"]
    approved = {checked_nb6_record(r["path"], review["vacuum"]["files"]) for r in review["vacuum"]["files"]}
    candidates = {checked_nb6_path(Path(TABLE) / f) for f in t.vacuum(retention_hours=0, dry_run=True, enforce_retention_duration=False)}
    assert candidates == approved
    return t.vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)
def delete_reviewed_orphan(value):
    p = checked_nb6_record(value, review["delta_orphans"])
    live = {checked_nb6_path(unquote(u.replace("file://", ""))) for u in DeltaTable(TABLE).file_uris()}
    assert p not in live
    p.unlink()
def delete_reviewed_manifest(value):
    p = checked_nb6_record(value, review["iceberg"]["manifest_lists_after_proposed_expiry"])
    live = {checked_nb6_path(s.manifest_list.replace("file://", "")) for s in cat.load_table("lake.maint").snapshots()}
    assert p not in live
    p.unlink()
'''


def main():
    target = REPO / "submission/notebooks/06_maintenance.ipynb"
    original = target.read_text(encoding="utf-8")
    nb = nbformat.reads(original, as_version=4)
    # Real execution of definitions only; no data mutation or repeat delete.
    namespace = {}
    exec(HELPERS, namespace)
    assert all(callable(namespace[n]) for n in ["vacuum_reviewed", "delete_reviewed_orphan", "delete_reviewed_manifest"])
    cell = nbformat.v4.new_code_cell(HELPERS)
    cell.execution_count = max(c.execution_count or 0 for c in nb.cells if c.cell_type == "code") + 1
    cell.outputs = []
    index = next(i for i, c in enumerate(nb.cells) if c.cell_type == "code" and c.source.startswith("import json, os, time")) + 1
    note = nbformat.v4.new_markdown_cell("Các helper dưới đây được ghi đầy đủ để đọc/kiểm tra code trong notebook. Chỉ định nghĩa hàm đã được thực thi ở bước bổ sung; không chạy lại VACUUM/delete. Execution count lớn hơn phản ánh bổ sung sau khi maintenance hoàn tất. Guard sẽ từ chối chạy lại trên trạng thái đã xử lý.")
    nb.cells[index:index] = [note, cell]
    nbformat.validate(nb)
    diff = list(difflib.unified_diff(original.splitlines(), nbformat.writes(nb).splitlines(), n=3))[2:]
    diff = ["@@" if line.startswith("@@") else line for line in diff]
    print("*** Begin Patch\n*** Update File: " + str(target) + "\n" + "\n".join(diff) + "\n*** End Patch")


if __name__ == "__main__":
    main()
