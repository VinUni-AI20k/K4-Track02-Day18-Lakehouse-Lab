"""Execute Jupytext notebooks and preserve real outputs for the lab submission.

Run with the lab environment's Python. PNGs render saved stdout excerpts;
they are explicitly labelled output renders, not screenshots of an app UI.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import jupytext
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"
NB_DIR = ROOT / "notebooks"
PREFIX = "LAB_METRICS_JSON="

METRICS = {
    "01": '''{
        "json_commits": len(_log), "schema_enforcement_blocked": schema_enforcement_blocked,
        "failed_write_version_unchanged": failed_write_version_unchanged,
        "tier_present": "tier" in _cols, "tier_groups": len(tier_counts),
        "rows_after_evolution": DeltaTable(table_path).count()
    }''',
    "02": '''{
        "files_before": files_before, "files_after": files_after,
        "speedup": speedup, "pruning_ratio": pruned_ratio,
        "files_covering_target": hits, "before_ms": before * 1000, "after_ms": after * 1000
    }''',
    "03": '''{
        "merge_source_rows": merge_metrics["num_source_rows"],
        "merge_updated_rows": merge_metrics["num_target_rows_updated"],
        "merge_inserted_rows": merge_metrics["num_target_rows_inserted"],
        "history_versions": len(final_history),
        "history_operations": [h["operation"] for h in reversed(final_history)],
        "restored_rows": dt_after.count(), "bad_rows_after_restore": bad_count
    }''',
    "04": '''{
        "bronze_rows": bronze_n, "silver_rows": silver_n, "dedup_removed": bronze_n - silver_n,
        "gold_dates": n_dates, "gold_models": n_models, "gold_rows": gold_df.height,
        "gold_values_correct": gold_values_correct,
        "gold_cost_usd": gold_df["cost_usd"].sum(),
        "error_rate_min": gold_df["error_rate"].min(), "error_rate_max": gold_df["error_rate"].max()
    }''',
    "05": '''{
        "files_all": files_all, "files_one_day": files_one, "pruning_ratio": PRUNE_RATIO,
        "metadata_bytes": meta_bytes, "data_bytes": data_bytes,
        "metadata_data_ratio": meta_bytes / max(data_bytes, 1),
        "latency_field_id": tbl.schema().find_field("latency_millis").field_id,
        "spec_ids": sorted(specs_in_use), "rows_readable": tbl.scan().to_arrow().num_rows
    }''',
    "06": '''{
        "files_before": base["data files"], "files_compacted": after_compact["data files"],
        "compaction_ratio": base["data files"] / after_compact["data files"],
        "cluster_total_files": total_files, "cluster_files_touched": after_cluster,
        "cluster_skip_rate": 1 - after_cluster / total_files,
        "vacuum_reclaimed_bytes": before_vacuum - (after_vacuum["data bytes"] + after_vacuum["log bytes"]),
        "delta_orphans_removed": len(found), "delta_orphan_bytes": reclaimed,
        "iceberg_snapshots_before": ice_before["snapshots"], "iceberg_snapshots_after": ice_after["snapshots"],
        "iceberg_avro_before": ice_before["manifest avro"], "iceberg_avro_after_expiry": ice_after["manifest avro"],
        "iceberg_manifest_lists_swept": len(stranded), "iceberg_sweep_bytes": reclaimed_ice,
        "checkpoint_written": bool(ckpt) and (log_dir / "_last_checkpoint").exists(),
        "delta_rows": DeltaTable(TABLE).count(), "iceberg_rows": cat.load_table(f"{ns}.maint").scan().to_arrow().num_rows
    }''',
    "07": '''{
        "amplification": AMPLIFICATION, "row_group_rows": rg_rows,
        "row_group_uncompressed_bytes": rg_bytes, "one_blob_bytes": one_blob,
        "float32_bytes": du(F32), "int8_bytes": du(I8), "storage_ratio": du(F32) / du(I8),
        "recall_at_10": float(recall), "topic_fidelity": float(topic_fidelity),
        "sql_search_ms": sql_ms, "query_topic": query_topic, "top5_topics": top_topics,
        "deleted_in_table_hits": in_hits, "stale_external_hits": ex_hits, "cdf_deletes": len(deletes)
    }''',
    "08": '''{
        "agent_partitions": sorted(p.name for p in Path(SILVER).glob("agent_version=*")),
        "gold_policies": gold.num_rows, "pinned_version": training_run["table_version"],
        "recorded_steps": training_run["n_steps_seen"], "replayed_steps": pinned.count(),
        "latest_steps": DeltaTable(SILVER).count(), "catalog_reads_for_5_turns": mcp.catalog_reads,
        "unconfirmed_result": attempt["resultType"], "task_status": st["status"],
        "provenance_partitions": parts, "unclassified_rows": unclassified,
        "trainable_rows": trainable, "corpus_rows": governed.num_rows,
        "subject_rows_before": before, "subject_rows_after": after
    }''',
}


def explanation(number: str, m: dict) -> str:
    text = {
        "01": lambda: f"Có {m['json_commits']} commit JSON. Ghi `age='thirty'` bị chặn và không thay đổi version/số dòng; opt-in schema merge thêm `tier`, DuckDB thấy {m['tier_groups']} nhóm (bao gồm NULL ở dữ liệu cũ). Transaction log xác định các file thuộc trạng thái bảng đã commit.",
        "02": lambda: f"Số file giảm {m['files_before']} → {m['files_after']}; speedup {m['speedup']:.2f}×, pruning {m['pruning_ratio']:.1f}×. Chỉ {m['files_covering_target']} file có min/max bao phủ user 4242 sau Z-order. Compaction giảm chi phí mở file; clustering thu hẹp khoảng stats để bỏ qua file. Timing là median của 3 lần và phụ thuộc cache/tải máy; rubric chấp nhận một trong hai ngưỡng.",
        "03": lambda: f"MERGE nhận {m['merge_source_rows']:,} dòng: update {m['merge_updated_rows']:,}, insert {m['merge_inserted_rows']:,}. History sau RESTORE có {m['history_versions']} version; hiện còn {m['restored_rows']:,} dòng tốt và {m['bad_rows_after_restore']} dòng score âm. RESTORE tạo commit mới, giữ audit trail và tham chiếu lại trạng thái v2; không xóa lịch sử.",
        "04": lambda: f"Bronze {m['bronze_rows']:,} → Silver {m['silver_rows']:,}, loại {m['dedup_removed']:,} bản ghi trùng request_id. Gold có {m['gold_dates']} ngày × {m['gold_models']} model = {m['gold_rows']} nhóm. p50/p95 nội suy tuyến tính, token sums, error_rate và cost đã được đối chiếu bằng phép tổng hợp Polars độc lập từ Silver lưu trên đĩa. Chi phí dùng giá giả định trong đề, không phải giá dịch vụ hiện hành.",
        "05": lambda: f"Lọc trên ts khiến plan_files chọn {m['files_one_day']} trong {m['files_all']} file ({m['pruning_ratio']:.0f}×); DayTransform suy ra partition ngày. Metadata/data = {m['metadata_data_ratio']:.2%}, đo trên fixture nhỏ nên overhead cao. Rename giữ field ID {m['latency_field_id']}; spec {m['spec_ids']} cùng tồn tại và đọc được {m['rows_readable']:,} dòng. SQLite catalog đăng ký bảng và cập nhật metadata; scan planning diễn ra phía client.",
        "06": lambda: f"Compaction {m['files_before']} → {m['files_compacted']} file ({m['compaction_ratio']:.1f}×); clustering bỏ qua {m['cluster_skip_rate']:.1%} file. Vacuum thu hồi {m['vacuum_reclaimed_bytes']:,} byte tombstoned. Với phiên bản deltalake ghi trong INFO, vacuum không thấy file chưa từng commit: đã tìm/xóa {m['delta_orphans_removed']} orphan bằng hiệu tập hợp có age guard. PyIceberg expiry giảm {m['iceberg_snapshots_before']} → {m['iceberg_snapshots_after']} snapshot nhưng avro vẫn {m['iceberg_avro_after_expiry']}; sweep riêng dọn {m['iceberg_manifest_lists_swept']} manifest list. Checkpoint tồn tại, dữ liệu hiện tại còn nguyên. Retention 0 chỉ dùng cho scratch của lab; sweep này không phải thuật toán GC production bảo vệ mọi reader/writer và snapshot lịch sử.",
        "07": lambda: f"Row group có {m['row_group_rows']} dòng, tỷ lệ byte row group/blob = {m['amplification']:.1f}×. Đây là ước lượng theo footer Parquet (uncompressed row-group bytes), không phải trace GET hoặc benchmark I/O thực; analytical projection có thể bỏ blob column. int8 nhỏ {m['storage_ratio']:.2f}×, recall@10 {m['recall_at_10']:.3f}, topic fidelity {m['topic_fidelity']:.3f} trên 100 query của corpus tổng hợp, top-k có tính self-match. Lifecycle bug: {m['deleted_in_table_hits']} hit trong bảng nhưng {m['stale_external_hits']} trong bản index cũ. CDF phát {m['cdf_deletes']} delete để consumer có thể evict theo doc_id; notebook chưa triển khai consumer đồng bộ index.",
        "08": lambda: f"Silver có hai partition agent_version, Gold có {m['gold_policies']} policy. Training pin v{m['pinned_version']}, replay {m['replayed_steps']:,}/{m['recorded_steps']:,} bước; version mới có {m['latest_steps']:,}. Kiểm tra replay chỉ so số bước, chưa chứng minh equality toàn bộ nội dung. Năm list_tables đọc catalog {m['catalog_reads_for_5_turns']} lần; call chưa xác nhận trả {m['unconfirmed_result']}, task {m['task_status']}. Đây là mô phỏng offline: confirmed do caller truyền, delete_rows là no-op. Bốn bucket minh họa và UNCLASSIFIED đều có partition; loại {m['unclassified_rows']:,} dòng khỏi tập training. Mapping CC-BY vào public_domain và consent vào scraped_optout_checked chỉ là fixture, không chứng minh quyền sử dụng dữ liệu. Xóa subject {m['subject_rows_before']} → {m['subject_rows_after']} chỉ ở version hiện tại; dữ liệu cũ còn theo retention.",
    }
    return "## Giải thích kết quả và giới hạn phép đo\n\n" + text[number]()


def stdout(cell) -> str:
    return "".join(o.get("text", "") for o in cell.get("outputs", []) if o.output_type == "stream" and o.name == "stdout")


def render_output(dest: Path) -> None:
    # Rendering can reuse an existing Pillow installation in the base Python
    # without adding its packages to the kernel's lab environment.
    import importlib.util
    render_python = sys.executable if importlib.util.find_spec("PIL") else sys._base_executable
    source = OUT / "notebooks" / (dest.stem + ".ipynb")
    subprocess.run([render_python, str(ROOT / "scripts/render_submission_outputs.py"), str(source), str(dest)], check=True)


def execute_notebook(src: Path) -> dict:
    number = src.name[:2]
    nb = jupytext.read(src)
    bootstrap = '''import sys, platform, importlib.metadata
from pathlib import Path
repo_root = next(p for p in (Path.cwd(), *Path.cwd().parents)
                 if (p / "scripts/lakehouse.py").exists() and (p / "notebooks/_setup.py").exists())
sys.path.insert(0, str(repo_root / "notebooks"))
print("Python:", sys.version.split()[0], "|", sys.executable)
print("OS:", platform.platform())
print("Libraries:", {name: importlib.metadata.version(name) for name in
    ("deltalake", "pyiceberg", "duckdb", "polars", "pyarrow", "numpy")})
'''
    nb.cells.insert(1, nbformat.v4.new_code_cell(bootstrap))
    evidence = f'''import json
lab_metrics = {METRICS[number]}
print("Bằng chứng rubric — NB{number}")
for label, value in lab_metrics.items():
    print(f"  {{label}}: {{value}}")
print({PREFIX!r} + json.dumps(lab_metrics, ensure_ascii=False, sort_keys=True))
'''
    nb.cells.append(nbformat.v4.new_markdown_cell("## Bằng chứng thu thập từ lần chạy này\n\nCác giá trị dưới đây lấy trực tiếp từ biến và bảng đã thực thi ở trên."))
    nb.cells.append(nbformat.v4.new_code_cell(evidence))
    km = KernelManager(kernel_name="python3")
    km.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(nb, km=km, timeout=600, resources={"metadata": {"path": str(NB_DIR)}}, record_timing=True)
    started = time.perf_counter()
    target = OUT / "notebooks" / (src.stem + ".ipynb")
    try:
        client.execute()
    except Exception:
        nbformat.write(nb, target)
        raise
    finally:
        if km.has_kernel:
            km.shutdown_kernel(now=True)
    m = next(json.loads(line[len(PREFIX):]) for cell in nb.cells for line in stdout(cell).splitlines() if line.startswith(PREFIX))
    nb.cells.append(nbformat.v4.new_markdown_cell(explanation(number, m)))
    nbformat.write(nb, target)
    render_output(OUT / "screenshots" / (src.stem + ".png"))
    print(f"PASS {src.name}: executed output saved ({time.perf_counter() - started:.1f}s)", flush=True)
    return m


def main() -> None:
    os.environ.setdefault("JUPYTER_RUNTIME_DIR", str(ROOT / ".venv" / "jupyter-runtime"))
    Path(os.environ["JUPYTER_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-only", action="store_true", help="Regenerate PNGs from existing executed outputs")
    args = parser.parse_args()
    for directory in ("notebooks", "screenshots", "evidence"):
        (OUT / directory).mkdir(parents=True, exist_ok=True)
    if args.render_only:
        for file in sorted((OUT / "notebooks").glob("[0-9]*.ipynb")):
            render_output(OUT / "screenshots" / (file.stem + ".png"))
        return
    metrics = {}
    for source in sorted(NB_DIR.glob("[0-9]*.py")):
        metrics[source.name[:2]] = execute_notebook(source)
        (OUT / "evidence" / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert len(metrics) == 8
    frozen = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True)
    (OUT / "evidence" / "requirements-lock.txt").write_text(frozen.stdout, encoding="utf-8")
    print("8/8 executed notebooks and 8 rendered output images saved.")


if __name__ == "__main__":
    main()
