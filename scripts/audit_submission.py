"""Check real executed deliverables against the assignment's unchanged thresholds."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    evidence = json.loads((OUT / "evidence" / "metrics.json").read_text(encoding="utf-8"))
    m = evidence["metrics"]
    checks = {}
    checks["all command gates return 0"] = all(x["returncode"] == 0 for x in evidence["results"].values())
    checks["24 instructor tests passed"] = "24 passed" in (OUT / "logs" / "pytest.txt").read_text(encoding="utf-8")
    checks["8 script notebooks passed"] = "8/8 passed" in (OUT / "logs" / "run_all.txt").read_text(encoding="utf-8")
    nbs = sorted((OUT / "notebooks").glob("*.ipynb"))
    checks["8 executed Jupyter notebooks"] = len(nbs) == 8
    for p in nbs:
        nb = nbformat.read(p, 4)
        cells = [c for c in nb.cells if c.cell_type == "code" and c.source.strip()]
        checks[p.stem + " executed, no error, output preserved"] = all(c.execution_count is not None for c in cells) and not any(o.output_type == "error" for c in cells for o in c.outputs) and any(c.outputs for c in cells)
        checks[p.stem + " explanation"] = any("Giải thích kết quả" in c.source for c in nb.cells if c.cell_type == "markdown")
    checks["NB1 log, enforcement, evolution, tier groups"] = m["01"]["commits"] >= 2 and m["01"]["schema_blocked"] and "tier" in m["01"]["columns"] and len(m["01"]["tier_counts"]) == 2
    a = m["02"]
    checks["NB2 small files, optimization, accepted threshold"] = a["files_before"] >= 100 and a["files_after"] < a["files_before"] and (a["speedup"] >= 3 or a["pruning_ratio"] >= 10)
    a = m["03"]
    checks["NB3 100K MERGE and RESTORE history"] = a["source_rows"] == 100_000 and a["versions"] >= 5 and {"MERGE", "RESTORE"} <= set(a["operations"]) and a["bad_rows"] == 0 and a["current_rows"] == 150_000
    a = m["04"]
    checks["NB4 dedup, date-model grid, Gold bounds"] = a["silver_rows"] < a["bronze_rows"] and a["dates"] >= 7 and a["models"] == 3 and a["gold_rows"] == 3*a["dates"] and all(r["p50_latency_ms"] <= r["p95_latency_ms"] and r["cost_usd"] > 0 and 0 <= r["error_rate"] <= 1 for r in a["gold"])
    a = m["05"]
    checks["NB5 hidden pruning, metadata, rename, two specs"] = a["pruning_ratio"] >= 5 and a["field_id"] == 4 and len(a["spec_ids"]) >= 2 and a["rows"] == 5500 and a["metadata_bytes"] > 0 and a["data_bytes"] > 0
    a = m["06"]
    checks["NB6 all five maintenance jobs"] = a["files_before"]/a["files_compacted"] >= 10 and a["skip_rate"] >= 0.5 and a["vacuum_reclaimed_bytes"] > 0 and a["delta_orphans_removed"] == 3 and a["iceberg_snapshots_after"] == 3 and a["manifest_lists_removed"] == 17 and bool(a["checkpoint"]) and a["current_rows"] == 100_000
    a = m["07"]
    checks["NB7 amplification, int8 quality, stale-index bug, CDF"] = a["amplification"] >= 5 and a["storage_ratio"] >= 3 and a["recall_at_10"] >= 0.8 and a["topic_fidelity"] >= 0.95 and a["table_deleted_hits"] == 0 and a["stale_index_hits"] > 0 and a["cdf_deletes"] == a["stale_index_hits"]
    a = m["08"]
    checks["NB8 replay, policies, cache, simulation, provenance, delete"] = a["pinned_steps"] == a["training_steps"] and a["current_steps"] > a["pinned_steps"] and len(a["gold"]) == 2 and a["catalog_reads"] == 1 and a["confirmation"] == "input_required" and a["task_status"] == "completed" and len(a["partitions"]) == 5 and a["unclassified_rows"] > 0 and a["subject_before"] > 0 and a["subject_after"] == 0
    shots = sorted((OUT / "screenshots").glob("*.png"))
    checks["8 PNG screenshots with notebook evidence"] = len(shots) == 8 and all(p.stat().st_size > 10_000 for p in shots)
    reflection = (OUT / "REFLECTION.md").read_text(encoding="utf-8")
    words = len(reflection.split())
    checks["reflection <= 200 whitespace words and AI declared"] = words <= 200 and "AI_USAGE.md" in reflection
    checks["required identity and AI declaration"] = all((OUT / p).exists() for p in ("INFO.md", "AI_USAGE.md", "bonus/ARCHITECTURE.md", "bonus/ARCHITECTURE.pdf"))
    for label, ok in checks.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    print(f"Reflection words: {words}")
    (OUT / "evidence" / "audit.json").write_text(json.dumps(dict(checks=checks, reflection_words=words), indent=2), encoding="utf-8")
    assert all(checks.values()), "Submission audit incomplete"

    a, b, c, d, e, f, g, h = [m[f"{i:02d}"] for i in range(1,9)]
    report = f"""# Báo cáo checkpoint - Đỗ Quốc An / 2A202602892

Lần thực thi: {evidence['executed_at']} (UTC+7). Số liệu lấy từ output Jupyter; [metrics.json](evidence/metrics.json) chứa bản máy đọc được. Đường lightweight, không suy ra Spark đã chạy. Việc chấm điểm do coach quyết định.

| Checkpoint | Kết quả thực tế | Bằng chứng |
|---|---|---|
| 0 | Smoke 9/9 PASS; Python 3.11; origin có tài khoản/tên repo đúng mẫu | [smoke](logs/smoke.txt), [environment](evidence/environment.json) |
| 1 | {a['commits']} commits; bad age bị chặn; 4 rows sau merge schema; tier premium=1, NULL=3 | [NB1](notebooks/01_delta_basics.ipynb), [ảnh](screenshots/nb01_delta_basics.png) |
| 2 | {b['files_before']} -> {b['files_after']} active files; speedup {b['speedup']:.2f}x; pruning {b['pruning_ratio']:.0f}x, 1 file chứa target | [NB2](notebooks/02_optimize_zorder.ipynb), [ảnh](screenshots/nb02_optimize_zorder.png) |
| 3 | MERGE {c['source_rows']:,} source rows; current {c['current_rows']:,}; {c['versions']} versions có RESTORE; score âm={c['bad_rows']} | [NB3](notebooks/03_time_travel.ipynb), [ảnh](screenshots/nb03_time_travel.png) |
| 4 | Bronze {d['bronze_rows']:,} -> Silver {d['silver_rows']:,}; Gold {d['dates']} ngày UTC x {d['models']} model = {d['gold_rows']} rows; p50<=p95, cost>0, error_rate hợp lệ | [NB4](notebooks/04_medallion.ipynb), [ảnh](screenshots/nb04_medallion.png) |
| 5 | {e['files_all']} -> {e['files_one_day']} file khi lọc ts; pruning {e['pruning_ratio']:.0f}x; field ID=4; specs {e['spec_ids']}; {e['rows']:,} rows đọc được | [NB5](notebooks/05_iceberg_catalog.ipynb), [ảnh](screenshots/nb05_iceberg_catalog.png) |
| 6 | Compaction {f['files_before']} -> {f['files_compacted']} ({f['files_before']/f['files_compacted']:.2f}x); skip {f['skip_rate']:.0%}; vacuum thu {f['vacuum_reclaimed_bytes']:,} bytes; 3 Delta orphan; Iceberg 20->3 snaps, sweep17 manifest lists; checkpoint có | [NB6](notebooks/06_maintenance.ipynb), [ảnh](screenshots/nb06_maintenance.png) |
| 7 | Amplification {g['amplification']:.2f}x; int8 nhỏ {g['storage_ratio']:.2f}x; recall@10 {g['recall_at_10']:.3f}; topic fidelity {g['topic_fidelity']:.3f}; deleted hits table=0/index={g['stale_index_hits']}; CDF {g['cdf_deletes']} deletes | [NB7](notebooks/07_vectors_multimodal.ipynb), [ảnh](screenshots/nb07_vectors_multimodal.png) |
| 8 | Pin v{h['pinned_version']}: {h['pinned_steps']:,} steps, current {h['current_steps']:,}; 2 policies; 5 list calls/1 read; input_required; task completed; 4 buckets + UNCLASSIFIED {h['unclassified_rows']}; subject8->0 | [NB8](notebooks/08_agents_provenance.ipynb), [ảnh](screenshots/nb08_agents_provenance.png) |
| 9 - phần local | 24/24 tests; 8/8 scripts; 8/8 Jupyter notebooks có output; 8 PNG; reflection {words} từ; INFO/AI usage/bonus đầy đủ | [pytest](logs/pytest.txt), [run-all](logs/run_all.txt), [audit](evidence/audit.json) |

## Giải thích số liệu

NB1 kiểm exception và tính nguyên vẹn sau bad write, không dùng PASS cố định. NB2 gom dữ liệu để min/max isolate user; tốc độ wall-clock có thể đổi theo cache/CPU, còn ngưỡng pruning 10x vẫn là lựa chọn rubric. NB3 RESTORE là commit mới, không xóa history.

NB4 loại {d['bronze_rows']-d['silver_rows']:,} retry; đặt session DuckDB UTC để không biến 7 ngày nguồn thành 8 ngày địa phương. Giá token trong notebook là fixture. NB5 metadata:data = {e['metadata_bytes']/e['data_bytes']*100:.1f}% trên toy table; lọc nguồn ts suy ra day(ts), rename giữ ID và spec evolution không rewrite hết dữ liệu.

NB6 file count là active file; bytes trên disk có tombstone cho tới vacuum. Với deltalake/PyIceberg trong requirements-lock, orphan chưa commit không có tombstone để vacuum biết; expiry giảm snapshot chưa dọn file, nên sweep riêng. Production sweep phải xét mọi snapshot còn giữ, reader/writer leases và age guard; scratch retention0 không phải khuyến nghị production.

Lưu ý output gốc NB6: dry-run báo0 B vì helper du nhận đường dẫn relative do vacuum trả về, chưa resolve từ table root; số bytes thu hồi trong báo cáo đo bằng chênh lệch toàn thư mục trước/sau vacuum, không dựa vào dự đoán0 B. Số Parquet trên disk sau orphan sweep gồm cả checkpoint trong _delta_log, nên có thể lớn hơn active data files; find_orphans đã loại _delta_log.

NB7 amplification là proxy từ row-group bytes chưa nén/one-blob, không phải traffic mạng đo được. Vector toy có cấu trúc topic, không phải embedding model thật. In-table delete không tự đồng bộ derived index; CDF ghi đủ8 sự kiện để consumer evict.

NB8 replay chỉ kiểm count, chưa so hash nội dung. MCP offline không server/authorization: cache list_tables, confirmed do caller cấp, delete_rows no-op. Mapping CC-BY->public_domain và consent->scraped_optout_checked là fixture hạn chế; không kết luận quyền sử dụng/tuân thủ pháp luật. Subject không còn trong version hiện tại nhưng version cũ còn dữ liệu.

## Phần còn phải làm để nộp

Các checkpoint kỹ thuật và bộ deliverable local đã được kiểm tra. Checkpoint0/9 về GitHub và nộp lớp chỉ hoàn tất khi bạn tự đọc/chạy theo RULES, xác nhận đây là fork cá nhân, commit/push, mở PR và gửi repo+PR+SHA qua kênh coach. Chưa có commit/PR nộp bài được tạo trong phiên này. Xem [HUONG_DAN_NOP_BAI.md](HUONG_DAN_NOP_BAI.md).

Bonus có 7 quyết định (mỗi quyết định loại 2 alternatives), diagram medallion, storage/compute math, 6 failure modes và MVP một tuần. Các sizing/price là giả định có nhãn; không tuyên bố đã benchmark production hay chạy PoC retention riêng.
"""
    (OUT / "CHECKPOINT_REPORT.md").write_text(report, encoding="utf-8")
    manifest = {str(p.relative_to(OUT)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'sha256.json'}
    (OUT / "evidence" / "sha256.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"All {len(checks)} checks PASS. Report and SHA256 manifest written.")


if __name__ == "__main__":
    main()
