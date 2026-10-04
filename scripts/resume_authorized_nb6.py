"""Execute ONLY the NB6 targets explicitly approved in REVIEW_20261004.json.

No table/catalog resets; no new orphan generation. Save every resumed cell
immediately to new evidence files. Preserve original notebooks/logs/screenshots.
"""
import argparse
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import unquote

import nbformat
from deltalake import DeltaTable

from prepare_remaining_review import REPO, DATA, DEST, fresh, scoped, git, write_new

REVIEW_SHA = "5f3353489c9260560459fe5dea33154702026336138dc7328f40d0fcd774cd7b"


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def definition(source, name):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    assert args.confirmation == "TÔI XÁC NHẬN THAO TÁC PHÁ HỦY NÀY"
    review_path = scoped(DEST / "REVIEW_20261004.json")
    assert digest(review_path) == REVIEW_SHA
    review = json.loads(review_path.read_text(encoding="utf-8"))
    table = scoped(review["vacuum"]["table"])
    assert table == scoped(DATA / "scratch" / "maint_events")
    records = review["vacuum"]["files"] + review["delta_orphans"] + review["iceberg"]["manifest_lists_after_proposed_expiry"]
    assert [len(review["vacuum"]["files"]), len(review["delta_orphans"]), len(review["iceberg"]["expire_snapshot_ids"]), len(review["iceberg"]["manifest_lists_after_proposed_expiry"])] == [211, 3, 17, 17]
    for record in records:
        p = scoped(record["path"])
        assert p.is_relative_to(DATA) and p.is_file()
        assert p.stat().st_size == record["bytes"] and digest(p) == record["sha256"]
        assert not git("ls-files", "--", p.relative_to(REPO).as_posix())
    os.environ["LAKEHOUSE_ROOT"] = str(DATA)
    import lakehouse as lh
    cat = lh.catalog("nb6")
    ice = cat.load_table("lake.maint")
    assert ice.metadata_location.replace("file://", "") == review["iceberg"]["metadata_to_retain"]["path"].replace("\\", "/") or scoped(ice.metadata_location.replace("file://", "")) == scoped(review["iceberg"]["metadata_to_retain"]["path"])
    assert digest(scoped(ice.metadata_location.replace("file://", ""))) == review["iceberg"]["metadata_to_retain"]["sha256"]
    assert [s.snapshot_id for s in ice.snapshots()[:-3]] == review["iceberg"]["expire_snapshot_ids"]
    assert [s.snapshot_id for s in ice.snapshots()[-3:]] == review["iceberg"]["keep_snapshot_ids"]
    assert ice.scan().to_arrow().num_rows == 2000
    dt = DeltaTable(str(table))
    assert dt.version() == review["vacuum"]["version"] == 201 and dt.count() == 100000
    approved_vacuum = {scoped(r["path"]) for r in review["vacuum"]["files"]}
    current_candidates = {scoped(table / f) for f in dt.vacuum(retention_hours=0, dry_run=True, enforce_retention_duration=False)}
    assert current_candidates == approved_vacuum
    live = {scoped(unquote(p.replace("file://", ""))) for p in dt.file_uris()}
    assert not live.intersection(approved_vacuum)
    active_hashes = {str(p): digest(p) for p in live}
    before_files = {scoped(p) for p in table.rglob("*") if p.is_file()}
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    runtime = fresh(DATA / "resume_nb6_20261004")
    target = scoped(DEST / "notebooks" / "06_maintenance.ipynb")
    backup = fresh(DEST / "history_nb6_20261004" / target.name)
    revision = fresh(DEST / "revisions_nb6_20261004" / target.name)
    final_log = fresh(DEST / "logs" / "nb6_completed_20261004.json")
    patch_path = fresh(DATA / "resume_nb6_20261004" / "notebook_updates.patch")
    original = target.read_text(encoding="utf-8")
    nb = nbformat.reads(original, as_version=4)
    original_assertion = nb.cells[33].source
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("xb") as f:
        f.write(target.read_bytes())
    runtime.mkdir()
    write_new(runtime / "preflight.json", json.dumps({"review_sha256": REVIEW_SHA, "git_status": status, "active_file_hashes": active_hashes}, ensure_ascii=False, indent=2))
    os.environ["IPYTHONDIR"] = str(runtime / "ipython")
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output
    shell = InteractiveShell()
    count = max(c.execution_count or 0 for c in nb.cells if c.cell_type == "code")
    outputs = []
    def run(cell):
        nonlocal count
        count += 1
        cell.execution_count = count
        with capture_output() as captured:
            result = shell.run_cell(cell.source, store_history=False)
        cell.outputs = []
        if captured.stdout:
            cell.outputs.append(nbformat.v4.new_output("stream", name="stdout", text=captured.stdout))
            print(captured.stdout, end="", flush=True)
        if captured.stderr:
            cell.outputs.append(nbformat.v4.new_output("stream", name="stderr", text=captured.stderr))
        for rich in captured.outputs:
            cell.outputs.append(nbformat.v4.new_output("display_data", data=rich.data, metadata=rich.metadata))
        error = result.error_before_exec or result.error_in_exec
        write_new(runtime / f"cell_{count:02d}.json", json.dumps(dict(cell), ensure_ascii=False, indent=2))
        if error:
            raise error
        outputs.extend(o.get("text", "") for o in cell.outputs if o.output_type == "stream")
    setup = '''import json, os, time
from pathlib import Path
from urllib.parse import unquote
import pyarrow as pa
from deltalake import DeltaTable
from lakehouse import ROOT, du, human, count_files, catalog
TABLE = str(ROOT / "scratch" / "maint_events")
review = json.loads((ROOT.parent / "submission/REVIEW_20261004.json").read_text(encoding="utf-8"))
base = {"data files": len(DeltaTable(TABLE, version=199).file_uris())}
after_compact = {"data files": len(DeltaTable(TABLE, version=200).file_uris())}
total_files = len(DeltaTable(TABLE).file_uris())
adds = pa.table(DeltaTable(TABLE).get_add_actions(flatten=True)).to_pylist()
after_cluster = sum(f["min.user_id"] <= 12345 <= f["max.user_id"] for f in adds)
before_vacuum = du(TABLE)
dt = DeltaTable(TABLE)
CAT, ns = "nb6", "lake"
cat = catalog(CAT)
ice = cat.load_table("lake.maint")
ice_meta = Path(ice.location().replace("file://", "")) / "metadata"
'''
    setup += "\n" + definition(nb.cells[4].source, "snapshot_metrics") + "\n"
    # Scoped callbacks are reflected in resumed cells and enforce the approved lists.
    def checked_remove(value, category):
        p = scoped(value)
        record = next(r for r in category if scoped(r["path"]) == p)
        assert p.stat().st_size == record["bytes"] and digest(p) == record["sha256"]
        if category is review["delta_orphans"]:
            assert p not in {scoped(unquote(u.replace("file://", ""))) for u in DeltaTable(str(table)).file_uris()}
        else:
            retained = {scoped(s.manifest_list.replace("file://", "")) for s in cat.load_table("lake.maint").snapshots()}
            assert p not in retained
        p.unlink()  # exact, reviewed, hash-verified target; explicitly authorized
    vacuum_result = {}
    def vacuum_reviewed():
        t = DeltaTable(str(table))
        assert t.version() == 201
        assert {scoped(table / f) for f in t.vacuum(retention_hours=0, dry_run=True, enforce_retention_duration=False)} == approved_vacuum
        for r in review["vacuum"]["files"]:
            assert digest(scoped(r["path"])) == r["sha256"]
        before_bytes = lh.du(str(table))
        result = t.vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)
        after_files = {scoped(p) for p in table.rglob("*") if p.is_file()}
        assert before_files - after_files == approved_vacuum
        assert all(digest(Path(p)) == h for p, h in active_hashes.items())
        vacuum_result.update(candidate_files=211, deleted_bytes=sum(r["bytes"] for r in review["vacuum"]["files"]), before_table_bytes=before_bytes, after_table_bytes=lh.du(str(table)))
        return result
    shell.user_ns.update(vacuum_reviewed=vacuum_reviewed,
                         delete_reviewed_orphan=lambda p: checked_remove(p, review["delta_orphans"]),
                         delete_reviewed_manifest=lambda p: checked_remove(p, review["iceberg"]["manifest_lists_after_proposed_expiry"]))
    setup_cell = nbformat.v4.new_code_cell(setup)
    run(setup_cell)
    for index in [14, 16, 18, 20, 22, 24, 26, 28, 29, 31, 33]:
        cell = nb.cells[index]
        assert cell.execution_count is None
        if index == 14:
            cell.source = cell.source.replace("dt.vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)", "vacuum_reviewed()  # rechecks the approved 211 paths and hashes")
        elif index == 16:
            cell.source = '''# The three exact orphans were already created in preparation; do not overwrite them.
planted = [Path(r["path"]) for r in review["delta_orphans"]]
assert all(p.is_file() for p in planted)
dt = DeltaTable(TABLE)
print(f"Rows reported by the table: {dt.count():,}")
print(f"Parquet files on disk: {count_files(TABLE)}; in current log: {len(dt.file_uris())}")
print(f"Planted orphans present: {len(planted)}")'''
        elif index == 20:
            cell.source = cell.source.replace("    os.remove(f)", "    delete_reviewed_orphan(f)")
            cell.source = cell.source.replace("found = find_orphans(TABLE)", "found = find_orphans(TABLE)\nassert {Path(p).resolve() for p in found} == {Path(r['path']).resolve() for r in review['delta_orphans']}")
        elif index == 22:
            cell.source = cell.source.replace("DeltaTable(TABLE).create_checkpoint()", "# Preserve existing automatic checkpoints; verify them below.")
        elif index == 24:
            cell.source = "# Preserve the prepared catalog with 20 snapshots; no reset or re-ingestion.\n" + definition(cell.source, "ice_metrics") + '\n\nice_before = ice_metrics("before expiry")'
        elif index == 26:
            cell.source = cell.source.replace("ice.maintenance.expire_snapshots()", "assert doomed_ids == review['iceberg']['expire_snapshot_ids']\nice.maintenance.expire_snapshots()")
        elif index == 29:
            cell.source = cell.source.replace("reclaimed_ice = sum(du(f) for f in stranded)", "assert {f.resolve() for f in stranded} == {Path(r['path']).resolve() for r in review['iceberg']['manifest_lists_after_proposed_expiry']}\nreclaimed_ice = sum(du(f) for f in stranded)")
            cell.source = cell.source.replace("    f.unlink()", "    delete_reviewed_manifest(f)")
        run(cell)
    assert nb.cells[33].source == original_assertion
    state = shell.user_ns
    assert all(state["checks"].values())
    assert all(not scoped(r["path"]).exists() for r in records)
    assert DeltaTable(str(table)).count() == 100000
    assert [s.snapshot_id for s in cat.load_table("lake.maint").snapshots()] == review["iceberg"]["keep_snapshot_ids"]
    assert cat.load_table("lake.maint").scan().to_arrow().num_rows == 2000
    assert all(digest(Path(p)) == h for p, h in active_hashes.items())
    result = {"authorization_scope": "NB6 review targets ONLY", "review_sha256": REVIEW_SHA,
              "vacuum": vacuum_result, "vacuum_net_reclaimed_bytes": vacuum_result["before_table_bytes"] - vacuum_result["after_table_bytes"],
              "delta_orphans_removed": 3, "delta_orphan_bytes_removed": sum(r["bytes"] for r in review["delta_orphans"]),
              "iceberg_snapshots_before": 20, "iceberg_snapshots_after": 3,
              "iceberg_manifest_lists_removed": 17, "iceberg_manifest_bytes_removed": state["reclaimed_ice"],
              "delta_current_rows": 100000, "iceberg_current_rows": 2000,
              "checks": state["checks"], "manual_checkpoint_created": False,
              "automatic_checkpoints_verified": True, "active_delta_data_hashes_unchanged": True}
    write_new(final_log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    write_new(DEST / "logs" / "nb6_resumed_20261004.txt", "\n\n".join(outputs))
    note = nbformat.v4.new_markdown_cell("### NB6 tiếp tục ngày 04/10/2026 sau xác nhận đúng danh sách\n\nĐã xác nhận riêng VACUUM/orphan/expiry/sweep. Cell dưới phục hồi biến bằng dữ liệu hiện có; không reset, không ghi đè baseline. Các callbacks chỉ thao tác đích đã duyệt và kiểm tra hash ngay trước thao tác. Checkpoint tự động được giữ nguyên. Bản notebook trước thao tác nằm trong history_nb6_20261004/.")
    nb.cells[14:14] = [note, setup_cell]
    nb.cells.append(nbformat.v4.new_markdown_cell("### Kết quả cuối NB6\n\nVACUUM thật đã chạy, xóa đúng 211 file; 3 orphan đã xử lý; Iceberg 20 → 3 snapshots và 17 manifest lists đã xử lý. Cả 9 assertion gốc PASS. Các đoạn ‘chưa hoàn tất’ phía trên là bằng chứng lần chạy trước. Số đo chi tiết: `submission/logs/nb6_completed_20261004.json`."))
    nb.metadata["lab_execution_status"] = "complete"
    nb.metadata["lab_resume_date"] = "2026-10-04"
    nbformat.validate(nb)
    revised = nbformat.writes(nb)
    write_new(revision, revised)
    assert target.read_text(encoding="utf-8") == original
    diff = list(difflib.unified_diff(original.splitlines(), revised.splitlines(), n=3))[2:]
    diff = ["@@" if line.startswith("@@") else line for line in diff]
    write_new(patch_path, "*** Begin Patch\n*** Update File: " + str(target) + "\n" + "\n".join(diff) + "\n*** End Patch\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
