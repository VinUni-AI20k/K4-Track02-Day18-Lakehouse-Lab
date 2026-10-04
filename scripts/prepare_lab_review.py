"""Preserve evidence and enumerate destructive targets without removing them."""
from __future__ import annotations

import contextlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import sys

import nbformat
import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import DeltaTable

from execute_submission_safe import REPO, DATA, DEST, inside, guards


def new_text(path, text):
    path = inside(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(text)


def main():
    os.environ["LAKEHOUSE_ROOT"] = str(DATA)
    guards()
    import lakehouse as lh
    import verify_lite as smoke

    # Keep all smoke artifacts; do not call main() because it deletes them.
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        smoke.check_delta()
        smoke.check_vectors()
        smoke.check_duckdb_delta_bridge()
        # Original check_iceberg assertions, with cleanup explicitly preserved.
        import inspect
        source = inspect.getsource(smoke.check_iceberg)
        last = source.rfind('    reset_catalog("smoke")')
        source = source[:last] + '    print("Smoke catalog preserved; cleanup not executed")\n' + source[last + len('    reset_catalog("smoke")'):]
        namespace = dict(smoke.__dict__)
        exec(compile(source, "<preserved-smoke-iceberg>", "exec"), namespace)
        namespace["check_iceberg"]()
        print("8/9 capability checks executed; CDF delete check pending authorization.")
    new_text(DEST / "logs" / "smoke_safe.txt", out.getvalue())

    table = inside(DATA / "scratch" / "maint_events")
    dt = DeltaTable(str(table))
    candidates = dt.vacuum(retention_hours=0, dry_run=True, enforce_retention_duration=False)
    vacuum = [inside(table / f) for f in candidates]
    assert all(f.is_file() and f.is_relative_to(table) for f in vacuum)
    plan = {
        "workspace": str(REPO),
        "status": "READ-ONLY REVIEW; NO DESTRUCTIVE OPERATIONS EXECUTED",
        "vacuum": {"table": str(table), "version": dt.version(),
                   "files": [{"path": str(f), "bytes": f.stat().st_size,
                              "tracked": False, "state": "new ignored synthetic file from this session"} for f in vacuum],
                   "total_bytes": sum(f.stat().st_size for f in vacuum),
                   "effect": "Physical removal would break older Delta versions; forbidden without a specific protection exception.",
                   "alternative": "Keep files; or review exact reversible quarantine destinations before authorizing moves."},
        "row_deletions": [],
        "not_yet_created": {
            "NB6 Iceberg": str(inside(DATA / "iceberg" / "nb6")),
            "NB7 CDF table": str(inside(DATA / "scratch" / "docs_cdf")),
            "smoke CDF table": str(inside(DATA / "scratch" / "_smoke_cdf")),
        },
    }
    for relative, subject in [("scratch/docs_intable", "user_042"), ("silver/training_corpus_governed", "user_007")]:
        p = inside(DATA / relative)
        t = DeltaTable(str(p))
        rows = t.to_pyarrow_table(filters=[("subject_id", "=", subject)])
        plan["row_deletions"].append({"table": str(p), "version": t.version(),
            "predicate": f"subject_id = '{subject}'", "count": rows.num_rows,
            "doc_ids": rows.column("doc_id").to_pylist(), "tracked": False,
            "state": "new ignored synthetic table from this session",
            "effect": "Remove only these rows from the current table via a new Delta commit; retain old physical files and version 0.",
            "recovery": "Delta restore to recorded version 0; no vacuum on these tables."})
    new_text(DEST / "DESTRUCTIVE_REVIEW.json", json.dumps(plan, indent=2, ensure_ascii=False))

    descriptions = {
        "01": "Bảng ban đầu có 3 hàng. Ghi `age='thirty'` bị chặn trong output thực tế; không dùng cờ PASS hardcode làm bằng chứng. `schema_mode='merge'` thêm `tier`, giữ NULL cho 3 hàng cũ và thêm hàng premium. Hai nhóm DuckDB là NULL và premium. Transaction log ghi protocol, metadata, add và commitInfo; add chứa thống kê và tên Parquet, không phải toàn bộ dữ liệu.",
        "02": "200 file trước tối ưu giảm còn 55 file. Median của 3 lần truy vấn giảm 492,3 → 34,2 ms, speedup 14,4×. Sau Z-order chỉ 1/55 khoảng min/max chứa user_id=4242, pruning ratio 55×. Compaction giảm overhead mở file; Z-order làm khoảng thống kê hẹp để engine bỏ qua file. Hai phép đo đều vượt ngưỡng, nhưng thời gian còn phụ thuộc cache và tải máy; pruning không đồng nghĩa chính xác số byte I/O thực tế.",
        "03": "MERGE 100.000 hàng chạy trong 0,14 s: 50.000 khóa khớp được cập nhật, 50.000 khóa mới được thêm. RESTORE về trạng thái v2 mất 0,03 s và tạo commit v4, không xóa lịch sử. History có 5 version; score<0 sau RESTORE bằng 0. Bản dữ liệu lỗi v3 vẫn có thể đọc vì chưa VACUUM. Đây là rollback có dấu vết audit.",
        "04": "Bronze có 200.000 hàng; Silver giữ 190.052, loại 9.948 hàng trùng (4,974%) theo request_id, chọn timestamp sớm nhất. Gold có 24 hàng = 8 ngày × 3 model, gồm p50/p95, token, error_rate và cost_usd. Dữ liệu sinh trải 7 ngày UTC; CAST timestamp có timezone sang DATE theo timezone của DuckDB trên máy làm xuất hiện ngày thứ 8. Đây là khác biệt ranh giới ngày, không phải thêm một ngày dữ liệu UTC. Chi phí dùng giá minh họa trong notebook, không phải giá hiện hành. Mã Silver giả định raw_json hợp lệ: comment nói bỏ malformed JSON nhưng query không có json_valid/TRY_CAST; chưa chứng minh xử lý dữ liệu lỗi JSON.",
        "05": "Catalog SQLite tạo và đăng ký bảng. Bộ lọc trên ts chọn 1/10 file, pruning 10× mà không cần lọc ts_day: planner suy ra partition từ day(ts). Rename latency_ms → latency_millis giữ field_id=4 và đọc được dữ liệu cũ; tier của 5.000 hàng cũ là NULL. Sau partition evolution, hai spec tồn tại và 5.500 hàng vẫn đọc được. Catalog → metadata JSON → manifest list → manifest → data cho phép planning bỏ qua công việc; tỷ lệ metadata/data ở output là phép đo của bảng nhỏ này, không suy rộng ra production.",
        "06": "Đã đo 100.000 hàng/200 commit. Compaction giảm 200 → 11 file (18,18×); clustering chọn 1/10 file, skip 90%. File cũ được tombstone nhưng vẫn tồn tại, nên số byte vật lý tăng sau rewrite. VACUUM dry-run liệt kê 211 file, chưa xóa file nào. Dòng gốc in 0 B do dùng du trên tên tương đối; số byte đúng được tính bằng table_path / filename trong DESTRUCTIVE_REVIEW.json. Chưa đo reclaim thật, orphan removal, snapshot expiry hay checkpoint; notebook chưa đạt đầy đủ rubric NB6. Không suy diễn hành vi expiry của phiên bản PyIceberg hiện tại từ lời giải thích có sẵn trong đề.",
        "07": "Đã đo random-access amplification 200× dựa trên kích thước row group so với blob cần lấy; đây là ước lượng độ hạt đọc, không phải đo traffic vật lý. int8 nhỏ hơn float32 5,8× trên đĩa (4× theo số byte phần tử); compression/metadata làm tỷ lệ khác 4. Recall@10=0,904 nghĩa là giữ khoảng 90,4% ID top-10 tham chiếu; topic fidelity=1,000 nghĩa là các láng giềng vẫn đúng chủ đề trong dữ liệu giả. SQL cosine search đã chạy. Chưa thực thi delete nên chưa tái hiện stale external index hoặc sự kiện CDF; không tuyên bố hoàn tất lifecycle check.",
        "08": "Silver có 1.578 bước, chia 2 partition agent_version; Gold có 2 policy. Training run pin v0: sau append, current v1 có 1.978 bước nhưng replay v0 vẫn có 1.578. Kiểm tra này chỉ so số hàng, chưa chứng minh nội dung giống từng byte. 5 lượt list_tables dùng 1 catalog read; input_required và polling là mô phỏng cục bộ, confirmed do caller đặt và delete_rows của mô phỏng là no-op. Corpus có 2.000 hàng, chọn 1.666 để train, loại 334 UNCLASSIFIED. Bốn bucket chỉ là nhãn minh họa: CC BY không phải public domain và user-owned+consent chưa chứng minh opt-out. Đã tìm 8 hàng user_007; chưa xóa. Đây không phải chứng nhận pháp lý hay MCP server thực.",
    }
    statuses = []
    for path in sorted((DEST / "notebooks").glob("*.ipynb")):
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        assert not any(o.output_type == "error" for c in nb.cells if c.cell_type == "code" for o in c.outputs)
        nb.cells.append(nbformat.v4.new_markdown_cell("### Giải thích kết quả thực tế — bản hỗ trợ AI cần người học kiểm tra\n\n" + descriptions[path.name[:2]]))
        if path.name.startswith("01"):
            log = inside(DATA / "scratch" / "users_delta" / "_delta_log" / "00000000000000000000.json")
            nb.cells.append(nbformat.v4.new_markdown_cell("### Bằng chứng commit JSON đã đọc từ đĩa\n\n`" + str(log) + "`\n\n```json\n" + log.read_text(encoding="utf-8") + "\n```"))
        # These notebooks were created during this task; preserve every cell/output.
        nbformat.write(nb, path)
        statuses.append(f"| {path.stem} | {nb.metadata['lab_execution_status']} |")
        output_text = "\n\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "stream")
        new_text(DEST / "logs" / f"{path.stem}.txt", output_text)
    versions = {name: importlib.metadata.version(name) for name in ["deltalake", "pyiceberg", "duckdb", "polars", "pyarrow", "numpy", "jupyterlab", "jupytext", "pytest", "IPython"]}
    new_text(DEST / "logs" / "environment.json", json.dumps({"python": sys.version, "platform": platform.platform(), "versions": versions}, ensure_ascii=False, indent=2))
    new_text(DEST / "INFO.md", "# Thông tin bài chạy\n\nHọ tên: Dương Xuân Vinh (suy ra từ tên repo, cần người học xác nhận).\n\nMSSV: 2A202602622. Mã bài: K4-Track02-Day18.\n\nĐường chạy: lightweight; Python " + platform.python_version() + "; " + platform.platform() + ". Chạy bằng IPython trong .venv, output lưu theo chuẩn ipynb.\n\nChi tiết phiên bản: [environment.json](logs/environment.json). Chưa commit/push.\n")
    new_text(DEST / "AI_USAGE.md", "# Phạm vi hỗ trợ AI\n\nCodex cài dependencies, sinh dữ liệu giả, thực thi code notebook trên máy này bằng IPython, lưu output thật và viết bản giải thích dựa trên output. Người học cần mở notebook, kiểm tra từng bước, tự giải thích và khai báo hỗ trợ này khi nộp. Không giả số liệu, không bỏ assertion hoặc hạ ngưỡng.\n\nThêm runner chỉ chấp nhận reset khi đích chưa tồn tại, dừng trước VACUUM thật và delete. NB1–NB5 hoàn tất; NB6–NB8 chưa hoàn tất. Smoke chỉ chạy 8/9 checks và giữ artifacts; pytest chạy 20/24 tests, loại 4 test phá hủy khỏi lần chạy này. Các phần chưa chạy không được coi là PASS.\n\nReflection cá nhân và ảnh chụp notebook vẫn cần hoàn thiện.\n")
    new_text(DEST / "RUN_STATUS.md", "# Trạng thái thực thi\n\n| Notebook | Trạng thái |\n|---|---|\n" + "\n".join(statuses) + "\n\n20 pytest PASS; 4 test chưa chạy vì có delete, expiry hoặc reset catalog. Smoke 8/9 checks PASS, chưa chạy CDF delete check. Chưa đạt yêu cầu full pytest, run-all và NB6–NB8.\n\n[Danh sách đích phá hủy chính xác](DESTRUCTIVE_REVIEW.json) liệt kê 211 file VACUUM với byte thực tế và các doc_id có thể bị xóa. Chưa thực thi thao tác phá hủy. File orphan và catalog nb6 chưa tạo nên chưa có danh sách đích để xin phép.\n\nNotebook có output và Markdown giải thích. Screenshots và reflection cá nhân chưa có.\n")
    print(f"Review ready: {len(vacuum)} files, {plan['vacuum']['total_bytes']:,} bytes; row targets: " + str([(x['predicate'], x['count']) for x in plan['row_deletions']]))


if __name__ == "__main__":
    main()
