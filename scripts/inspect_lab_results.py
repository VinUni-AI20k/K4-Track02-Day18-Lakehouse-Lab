"""Read-only checks beyond the notebook's PASS flags."""
import json
from pathlib import Path

import duckdb
import nbformat
from deltalake import DeltaTable

from execute_submission_safe import DATA, DEST, inside

con = duckdb.connect()
gold = DeltaTable(str(DATA / "gold" / "llm_daily_metrics")).to_pyarrow_table()
silver = DeltaTable(str(DATA / "silver" / "llm_calls")).to_pyarrow_table()
con.register("gold", gold)
con.register("silver", silver)
timezone = con.sql("SELECT current_setting('TimeZone')").fetchone()[0]
checks = {
    "gold_has_8_dates_and_3_models": con.sql("SELECT count(DISTINCT date)=8 AND count(DISTINCT model)=3 AND count(*)=24 FROM gold").fetchone()[0],
    "every_date_has_all_3_models": con.sql("SELECT bool_and(n=3) FROM (SELECT date, count(DISTINCT model) n FROM gold GROUP BY date)").fetchone()[0],
    "gold_metrics_nonnull_and_sensible": con.sql("SELECT bool_and(p50_latency_ms IS NOT NULL AND p95_latency_ms>=p50_latency_ms AND error_rate BETWEEN 0 AND 1 AND cost_usd>0) FROM gold").fetchone()[0],
    "silver_request_ids_unique": con.sql("SELECT count(*)=count(DISTINCT request_id) FROM silver").fetchone()[0],
    "silver_local_dates_match_ts_cast": con.sql("SELECT bool_and(date=CAST(ts AS DATE)) FROM silver").fetchone()[0],
}
log_dir = DATA / "scratch" / "maint_events" / "_delta_log"
checkpoint_files = sorted(p.name for p in log_dir.glob("*.checkpoint.parquet"))
checks["delta_checkpoints_already_exist"] = bool(checkpoint_files) and (log_dir / "_last_checkpoint").is_file()
for notebook in sorted((DEST / "notebooks").glob("*.ipynb")):
    nb = nbformat.read(notebook, as_version=4)
    nbformat.validate(nb)
    checks[notebook.stem + "_output_has_no_error"] = not any(o.output_type == "error" for c in nb.cells if c.cell_type == "code" for o in c.outputs)
assert all(checks.values()), checks
result = {"duckdb_timezone": timezone, "checks": checks, "existing_checkpoint_files": checkpoint_files,
          "note": "Checkpoints were created automatically during writes. Manual NB6 checkpoint cell remains unexecuted."}
target = inside(DEST / "logs" / "additional_checks.json")
with target.open("x", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=2))
