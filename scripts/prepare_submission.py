"""Run gates and real Jupyter kernels; preserve outputs and measured evidence."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"
METRICS = {
    "01": "dict(commits=len(_log), schema_blocked=schema_blocked, columns=_cols, tier_counts=tier_counts, rows=dt.count())",
    "02": "dict(files_before=files_before, files_after=files_after, target_files=hits, speedup=speedup, pruning_ratio=pruned_ratio)",
    "03": "dict(versions=len(final_history), operations=ops, source_rows=updates.height, current_rows=dt_after.count(), bad_rows=bad_count, v0_rows=v0_count)",
    "04": "dict(bronze_rows=bronze_n, silver_rows=silver_n, dates=n_dates, models=n_models, gold_rows=gold_df.height, gold=gold_df.sort(['date','model']).to_dicts())",
    "05": "dict(files_all=files_all, files_one_day=files_one, pruning_ratio=PRUNE_RATIO, metadata_bytes=meta_bytes, data_bytes=data_bytes, field_id=4, spec_ids=sorted(specs_in_use), rows=tbl.scan().to_arrow().num_rows)",
    "06": "dict(files_before=base['data files'], files_compacted=after_compact['data files'], files_clustered=total_files, target_files=after_cluster, skip_rate=1-after_cluster/max(total_files,1), vacuum_reclaimed_bytes=before_vacuum-after_vacuum['data bytes']-after_vacuum['log bytes'], delta_orphans_removed=len(found), iceberg_snapshots_before=ice_before['snapshots'], iceberg_snapshots_after=ice_after['snapshots'], manifest_lists_removed=len(stranded), iceberg_reclaimed_bytes=reclaimed_ice, checkpoint=[p.name for p in ckpt], current_rows=DeltaTable(TABLE).count())",
    "07": "dict(amplification=AMPLIFICATION, float32_bytes=du(F32), int8_bytes=du(I8), storage_ratio=du(F32)/du(I8), recall_at_10=float(recall), topic_fidelity=float(topic_fidelity), table_deleted_hits=in_hits, stale_index_hits=ex_hits, cdf_deletes=len(deletes), sql_ms=sql_ms)",
    "08": "dict(pinned_version=training_run['table_version'], pinned_steps=pinned.count(), current_steps=DeltaTable(SILVER).count(), training_steps=training_run['n_steps_seen'], catalog_reads=mcp.catalog_reads, confirmation=attempt['resultType'], task_status=st['status'], partitions=parts, trainable_rows=trainable, unclassified_rows=unclassified, subject_before=before, subject_after=after, gold=gold.to_pylist())",
}
EXPLANATIONS = {
    "01": "Delta ghi các action vào transaction log. Ghi age='thirty' phải phát sinh lỗi và không đổi version/số dòng. Thêm tier chỉ được phép với schema_mode='merge'; các dòng cũ có tier=NULL.",
    "02": "Compaction giảm chi phí mở file; Z-order gom user_id để min/max giúp loại file. Pruning ratio là số file hiện tại chia số file có khoảng giá trị chứa user cần tìm. Thời gian chịu ảnh hưởng cache, CPU và I/O; rubric chấp nhận speedup hoặc pruning.",
    "03": "100.000 dòng nguồn MERGE gồm 50.000 cập nhật và 50.000 chèn. RESTORE về v2 tạo v4, giữ audit history và loại 50 dòng score âm khỏi trạng thái hiện tại; v0 vẫn có 100.000 dòng.",
    "04": "Bronze giữ raw JSON, Silver giữ lần đầu của mỗi request_id, Gold tổng hợp theo ngày/model. p50/p95 được tính bằng quantile liên tục; error_rate là tỷ lệ status khác ok. Chi phí dùng giá minh họa trong lab, không phải giá dịch vụ hiện hành.",
    "05": "Predicate lọc ts được suy ra day(ts) từ partition spec nên plan_files giảm mà người dùng không viết ts_day. Rename giữ field ID 4 và không rewrite data. Hai spec cùng tồn tại; tỷ lệ metadata:data lớn trên bảng nhỏ là overhead của batch/commit.",
    "06": "Các số files là file đang active; bytes trên storage còn chứa file tombstoned trước VACUUM. Trong phiên bản thư viện được ghi ở INFO, vacuum không phát hiện orphan chưa commit. Snapshot expiry của PyIceberg giảm tham chiếu nhưng cần sweep manifest list riêng. Retention 0 chỉ dùng scratch; production phải bảo vệ reader, writer và mọi snapshot được giữ.",
    "07": "Amplification lấy kích thước row group chưa nén trong footer chia một blob; đây là proxy granularity, không phải đo network bytes của mọi reader. Analytical projection bỏ blob column. Int8 giảm storage nhưng cần đo recall và topic fidelity trên corpus thật. Index là bản sao có thể rebuild; CDF delete cần được áp dụng để ngăn trả doc đã xóa.",
    "08": "Pin version giúp truy vấn đúng số bước training đã đọc, dù current version tăng. Đây là replay số dòng, chưa chứng minh nội dung/hash bằng nhau. MCP là mô phỏng offline: cache nằm ở list_tables, confirmed do caller truyền, delete_rows là no-op. Bốn provenance bucket là fixture; CC-BY không phải public domain và consent không chứng minh opt-out. Xóa subject hiện tại không xóa version cũ.",
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for sub in ("notebooks", "logs", "evidence", "screenshots"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    gate_file = OUT / "evidence" / "gates.json"
    results = json.loads(gate_file.read_text(encoding="utf-8")) if "--notebooks-only" in sys.argv else {}
    gates = (
        ("smoke", ["scripts/verify_lite.py"]),
        ("generate_data", ["scripts/generate_data_lite.py"]),
        ("generate_ai_data", ["scripts/generate_ai_data.py"]),
        ("pytest", ["-m", "pytest", "--basetemp=.pytest_tmp"]),
        ("run_all", ["scripts/run_all.py"]),
    )
    for name, command in (() if "--notebooks-only" in sys.argv else gates):
        print(f"Running {name} ...", flush=True)
        start = time.perf_counter()
        result = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        (OUT / "logs" / f"{name}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
        results[name] = dict(returncode=result.returncode, seconds=round(time.perf_counter()-start, 2))
        print(result.stdout[-1700:], flush=True)
        if result.returncode:
            print(result.stderr[-5000:], flush=True)
            return result.returncode
    gate_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    import jupytext
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager

    kernel_root = ROOT / ".venv" / "share" / "jupyter" / "kernels"
    kernel_dir = kernel_root / "lab18"
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "kernel.json").write_text(json.dumps(dict(argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"], display_name="Lab18 Python", language="python")), encoding="utf-8")
    metrics = {}
    for source in sorted((ROOT / "notebooks").glob("[0-9]*.py")):
        nb = jupytext.read(source)
        key = source.name[:2]
        bootstrap = "from pathlib import Path\nimport sys\n_candidates = [Path.cwd(), *Path.cwd().parents]\n_lab_root = next(p for p in _candidates if (p / 'notebooks' / '_setup.py').exists())\nsys.path.insert(0, str(_lab_root / 'notebooks'))"
        nb.cells.insert(1, nbformat.v4.new_code_cell(bootstrap))
        nb.cells.append(nbformat.v4.new_markdown_cell("## Giải thích kết quả và giới hạn\n\n" + EXPLANATIONS[key]))
        nb.cells.append(nbformat.v4.new_code_cell("import json as _json\n_measured = " + METRICS[key] + "\nprint('MEASURED_JSON=' + _json.dumps(_measured, ensure_ascii=False, default=str))"))
        nb.metadata["kernelspec"] = dict(name="lab18", display_name="Lab18 Python", language="python")
        km = KernelManager(kernel_name="lab18", kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_root)]))
        client = NotebookClient(nb, timeout=600, km=km, resources={"metadata": {"path": str(ROOT / "notebooks")}})
        print(f"Executing Jupyter {source.stem} ...", flush=True)
        start = time.perf_counter()
        try:
            client.execute()
        finally:
            nbformat.write(nb, OUT / "notebooks" / f"{source.stem}.ipynb")
            if km.has_kernel:
                km.shutdown_kernel(now=True)
        text = "\n".join(output.get("text", "") for cell in nb.cells for output in cell.get("outputs", []))
        (OUT / "logs" / f"{source.stem}.txt").write_text(text, encoding="utf-8")
        metric_line = next(line for line in text.splitlines() if line.startswith("MEASURED_JSON="))
        metrics[key] = json.loads(metric_line.split("=", 1)[1])
        results[source.stem] = dict(returncode=0, seconds=round(time.perf_counter()-start, 2))
        print(f"PASS {source.stem}: {results[source.stem]['seconds']}s", flush=True)

    stamp = datetime.now(ZoneInfo("Asia/Bangkok")).isoformat()
    (OUT / "evidence" / "metrics.json").write_text(json.dumps(dict(executed_at=stamp, metrics=metrics, results=results), ensure_ascii=False, indent=2), encoding="utf-8")
    env = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    (ROOT / "requirements-lock.txt").write_text(env, encoding="utf-8")
    (OUT / "evidence" / "environment.json").write_text(json.dumps(dict(python=sys.version, os=platform.platform(), executable=sys.executable, executed_at=stamp), indent=2), encoding="utf-8")
    print("All gates and 8 executed notebooks preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
