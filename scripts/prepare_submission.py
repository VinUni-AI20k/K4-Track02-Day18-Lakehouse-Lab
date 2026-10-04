"""Execute the eight required notebooks and save traceable submission evidence.

Run with .venv/bin/python scripts/prepare_submission.py. No bonus is generated.
The HTML evidence views contain verbatim output excerpts, for browser screenshots.
"""
from __future__ import annotations

import html
import json
import platform
import sys
from datetime import datetime, timezone, timedelta
from importlib.metadata import distributions
from pathlib import Path

import jupytext
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"

EXPLANATIONS = {
    1: "Delta ghi transaction vào JSON log. Ghi age='thirty' bị chặn và không tăng version hay số dòng. Thêm tier cần schema_mode='merge'; dữ liệu cũ có tier=NULL, dữ liệu mới có premium nên query trả hai nhóm. Bằng chứng dưới đây gồm đường dẫn log và nguyên văn commit v0.",
    2: "200 micro-batch tạo 200 file nhỏ. Compaction giảm số file; Z-order gom user_id để min/max loại file không chứa 4242. Pruning ratio là tổng file sau tối ưu chia số file có khoảng chứa user đích; đây là file có thể cần đọc, không phải số dòng khớp. Speedup dùng median ba lần, có thể biến động do cache và tải máy; rubric chấp nhận speedup ≥3× hoặc pruning ≥10×.",
    3: "MERGE xử lý 100.000 dòng nguồn: 50.000 update và 50.000 insert, thành 150.000 dòng. Time travel v0 vẫn có 100.000 dòng. RESTORE về trạng thái v2 tạo commit v4, giữ lịch sử v0–v3; số dòng score<0 hiện tại phải bằng 0.",
    4: "Bronze giữ 200.000 bản ghi thô. Silver chọn lần xuất hiện đầu theo request_id, loại retry trùng và partition theo ngày. Gold tổng hợp từng ngày/model, tính percentile liên tục p50/p95, tỷ lệ status khác ok và chi phí theo bảng giá minh họa có sẵn trong lab. Kiểm tra đủ mọi cặp ngày/model, p50≤p95, cost>0 và error_rate∈[0,1]. Đây là dữ liệu giả, không phải benchmark hay giá dịch vụ hiện hành.",
    5: "SqlCatalog SQLite quản lý namespace, đăng ký bảng và con trỏ metadata. day(ts) cho phép filter trực tiếp trên ts; plan_files chọn file một ngày thay vì cả 10 ngày. Rename latency_ms giữ field_id=4 và không rewrite dữ liệu. Spec mới thêm model cùng tồn tại với spec cũ; vẫn đọc được 5.500 dòng. Metadata:data được tính bằng tổng byte metadata chia byte data; tỷ lệ cao ở bảng nhỏ không thể suy ra trực tiếp cho production. Phép tính chi phí trong notebook là giả định minh họa của đề.",
    6: "Compaction giảm file live nhưng tạm tăng dung lượng vật lý vì file cũ được tombstone. Clustering được đo bằng min/max, không chỉ stopwatch. VACUUM thu hồi file đã tombstone, nhưng trong delta-rs phiên bản đang chạy không tìm ba orphan chưa commit; phép hiệu file trên đĩa và file được tham chiếu, có age guard, tìm và xóa chúng. PyIceberg expiry giảm 20→3 snapshot nhưng chưa xóa manifest list vật lý; sweep riêng dọn file stranded. Các phép dọn chỉ chạy trên bảng scratch của lab; production cần bảo vệ cả snapshot còn giữ và writer đang chạy. Checkpoint và _last_checkpoint hỗ trợ reader giảm replay JSON.",
    7: "Amplification dùng byte row group trong footer chia kích thước một blob; đây là ước lượng theo granularity row group, không phải đo byte mạng của một truy vấn. Query chỉ chọn topic tránh đọc blob nhờ column pruning. int8 tiết kiệm dung lượng nhưng phải kiểm tra recall@10 và topic fidelity trên 100 query của corpus giả; self-match được giữ theo bài mẫu. SQL cast list<float> thành FLOAT[256] vì đường Delta không giữ fixed-size vector. Xóa user_042 làm in-table hết hit nhưng external index cũ vẫn còn hit; CDF mang doc_id của delete để index có thể đồng bộ. Notebook minh họa feed, chưa triển khai consumer tự đồng bộ.",
    8: "Silver partition theo hai agent_version, Gold có cả hai policy. Training pin version trước append; replay đối chiếu số bước, chưa chứng minh equality toàn bộ nội dung. Lớp MCP chạy offline: năm list_tables chỉ đọc catalog một lần, destructive call trả input_required, task polling hoàn tất. confirmed do caller truyền và delete_rows là no-op, nên không phải authorization production hay MCP server thật. Bốn bucket là fixture minh họa; CC-BY-4.0 cần ghi công, không phải public domain, và consent không chứng minh đã kiểm tra scraping opt-out. UNCLASSIFIED bị loại khỏi trainable set. Xóa subject chỉ xác nhận version hiện tại; version cũ vẫn chứa dữ liệu.",
}

SUMMARIES = {
    1: '''print(f"Schema enforcement blocked: {schema_enforcement_blocked}; failed write left v{version_before_bad_write} and 3 rows unchanged")
print("Schema after merge:", _cols)
print("Tier groups:", tier_counts)
print("Log directory:", _Path(table_path) / "_delta_log")
print("JSON commits:", [p.name for p in _log])
print("Commit v0 contents:\\n" + _log[0].read_text())''',
    2: '''print(f"Files before={files_before}; after compact+ZORDER={files_after}")
print(f"Median before={before*1000:.3f} ms; after={after*1000:.3f} ms; speedup={speedup:.2f}x")
print(f"Target user={TARGET_USER}; candidate files={hits}/{files_after}; pruning={pruned_ratio:.2f}x")
print("Candidate user_id ranges:", [(mn, mx) for mn, mx in sorted(ranges) if mn <= TARGET_USER <= mx])''',
    3: '''print("MERGE 100K metrics:", merge_metrics)
print(f"Time travel v0 rows={v0_count}; current rows={dt_after.count()}; score<0={bad_count}")
print("History after RESTORE:")
for h in final_history:
    print(f"v{h['version']}: {h['operation']}")''',
    4: '''print(f"Storage: Bronze={BRONZE}\\nSilver={SILVER}\\nGold={GOLD}")
print(f"Bronze={bronze_n}; Silver={silver_n}; dropped={bronze_n-silver_n}")
print(f"Gold: {n_dates} dates x {n_models} models = {gold_df.height} rows")
print(gold_df.sort(["date", "model"]).select(["date", "model", "p50_latency_ms", "p95_latency_ms", "cost_usd", "error_rate"]).write_csv())
print("Gold checks:", gold_checks)''',
    5: '''print(f"Catalog={type(cat).__name__}; table={tbl.name()}; day(ts) partition")
print(f"Plan files: all={files_all}; one day={files_one}; pruning={PRUNE_RATIO:.1f}x")
print(f"Metadata={meta_bytes} bytes; data={data_bytes} bytes; metadata:data={meta_bytes/max(data_bytes,1):.4f}")
print(f"Tree: metadata JSON -> {snaps.num_rows} snapshot manifest lists -> {mans.num_rows} manifests -> {files.num_rows} data files (before evolution)")
print("Field IDs after rename:", [(f.field_id, f.name) for f in tbl.schema().fields])
print("Partition spec IDs in use:", sorted(specs_in_use))
print("Rows across specs:", tbl.scan().to_arrow().num_rows)''',
    6: '''print(f"Compaction: {base['data files']} -> {after_compact['data files']} files; {base['data files']/after_compact['data files']:.2f}x fewer")
print(f"Clustering: touched {before_cluster} -> {after_cluster}/{total_files}; skip={(1-after_cluster/total_files)*100:.2f}%")
print(f"Delta vacuum reclaimed={before_vacuum-after_vacuum['data bytes']-after_vacuum['log bytes']} bytes")
print(f"Delta orphans found/removed={len(found)}; remaining={len(find_orphans(TABLE))}")
print(f"Iceberg snapshots={ice_before['snapshots']} -> {ice_after['snapshots']}; avro before/after expiry={ice_before['manifest avro']}/{ice_after['manifest avro']}")
print(f"Stranded manifest lists removed={len(stranded)}; reclaimed={reclaimed_ice} bytes; remaining={len(find_iceberg_orphans(ice))}")
print("Checkpoint:", [p.name for p in ckpt]); print("_last_checkpoint:", (log_dir / '_last_checkpoint').exists())
print("Current Delta rows:", DeltaTable(TABLE).count()); print("Current Iceberg rows:", ice.scan().to_arrow().num_rows)''',
    7: '''print(f"Row group={rg_rows} rows / {rg_bytes} bytes; blob={one_blob} bytes; amplification={AMPLIFICATION:.2f}x")
print(f"Float32={du(F32)} bytes; int8={du(I8)} bytes; ratio={du(F32)/du(I8):.3f}x")
print(f"Recall@10={recall:.3f}; topic fidelity={topic_fidelity:.3f}")
print("SQL top-5 neighbours:", hits)
print(f"Lifecycle: erased docs in table={in_hits}; stale external index={ex_hits}; CDF deletes={len(deletes)}")''',
    8: '''print("Silver partitions:", sorted(p.name for p in Path(SILVER).glob('agent_version=*')))
print("Gold policies:", gold.to_pylist())
print(f"Pinned version={training_run['table_version']}; training steps={training_run['n_steps_seen']}; replay steps={pinned.count()}")
print(f"5 list_tables calls -> {mcp.catalog_reads} catalog read; destructive call={attempt['resultType']}; task={st['status']}")
print("Provenance partitions:", parts)
print(f"Trainable={trainable}/{governed.num_rows}; excluded UNCLASSIFIED={unclassified}")
print(f"Current-version deletion of {SUBJECT}: {before} -> {after}; version {corpus_version} -> {after_dt.version()}")''',
}

BOOTSTRAP = '''import sys
from pathlib import Path
_repo = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "scripts" / "lakehouse.py").is_file())
sys.path.insert(0, str(_repo / "notebooks"))
'''


def main():
    for d in ("notebooks", "evidence", "screenshots"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    reports = []
    for i, source in enumerate(sorted((ROOT / "notebooks").glob("[0-9]*.py")), 1):
        nb = jupytext.read(source)
        first_code = next(c for c in nb.cells if c.cell_type == "code")
        first_code.source = BOOTSTRAP + first_code.source
        nb.cells.append(nbformat.v4.new_markdown_cell("## Giải thích kết quả và giới hạn\n\n" + EXPLANATIONS[i]))
        nb.cells.append(nbformat.v4.new_code_cell(SUMMARIES[i]))
        nb.metadata.kernelspec = {"display_name": "Python 3 (lab .venv)", "language": "python", "name": "python3"}
        dest = OUT / "notebooks" / (source.stem + ".ipynb")
        print(f"Executing {source.name}", flush=True)
        NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
        nbformat.write(nb, dest)
        outputs = "".join(o.get("text", "") for o in nb.cells[-1].get("outputs", []))
        transcript = "\n\n".join("".join(o.get("text", "") for o in c.get("outputs", [])) for c in nb.cells if c.cell_type == "code")
        # Plain-text transcripts trim padding; notebook cell outputs stay exact.
        transcript = "\n".join(line.rstrip() for line in transcript.splitlines()) + "\n"
        (OUT / "evidence" / (source.stem + ".txt")).write_text(transcript)
        page = f'''<!doctype html><html lang="vi"><meta charset="utf-8"><title>NB{i} — Lakehouse Lab evidence</title>
<style>body{{font:16px Arial,sans-serif;margin:32px;color:#17212d;background:white;max-width:1460px}}h1{{font-size:24px}}p{{line-height:1.5}}pre{{font:14px monospace;white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #bcc6d1;padding:18px;background:#f5f7fa}}</style>
<h1>NB{i} · {html.escape(source.stem)} · Mai Huy Hoang · 2A202602685</h1>
<p>Verbatim output from the executed notebook: submission/notebooks/{html.escape(dest.name)}</p>
<pre>{html.escape(outputs)}</pre><p>{html.escape(EXPLANATIONS[i])}</p></html>'''
        (OUT / "evidence" / (source.stem + ".html")).write_text(page)
        reports.append(f"## NB{i} — {source.stem}\n\n```text\n{outputs.strip()}\n```\n\n{EXPLANATIONS[i]}\n")
        print(f"Saved {dest.relative_to(ROOT)}", flush=True)
    (OUT / "RESULTS.md").write_text("# Kết quả phần bắt buộc\n\nSố liệu trích từ các notebook đã thực thi; dữ liệu đầu vào do scripts của đề bài sinh.\n\n" + "\n".join(reports))
    env = {"python": sys.version, "platform": platform.platform(), "executed_at": datetime.now(timezone(timedelta(hours=7))).isoformat(), "packages": dict(sorted((d.metadata["Name"], d.version) for d in distributions()))}
    (OUT / "evidence" / "environment.json").write_text(json.dumps(env, indent=2))
    (OUT / "evidence" / "requirements-lock.txt").write_text("\n".join(f"{name}=={version}" for name, version in env["packages"].items()) + "\n")


if __name__ == "__main__":
    main()
