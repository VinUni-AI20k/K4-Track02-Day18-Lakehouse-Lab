# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # NB3 — Time Travel + MERGE Upsert (lightweight)
#
# Maps to slide §3 + deliverable bullet 3.
#
# > Spark equivalent: `option("versionAsOf", N)` ↔ `DeltaTable(path, version=N)`
# >                   `MERGE INTO ...`           ↔ `dt.merge(source, predicate)`

# %%
import _setup  # noqa: F401  -- adds scripts/ to sys.path
import time
import polars as pl
from deltalake import DeltaTable, write_deltalake
from lakehouse import path, reset

table_path = path("scratch", "customers_tt")
reset(table_path)

# %% [markdown]
# ## 1. Build version history
# v0: initial 100K · v1: schema add · v2: MERGE upsert · v3: bad data

# %%
# v0 — initial load
v0 = pl.DataFrame({
    "customer_id": list(range(100_000)),
    "status":      ["active"] * 100_000,
    "score":       [i % 1000 for i in range(100_000)],
})
write_deltalake(table_path, v0.to_arrow(), mode="overwrite")

# v1 — add `tier` column (schema evolution)
v1 = (pl.from_arrow(DeltaTable(table_path).to_pyarrow_table())
        .with_columns(
            pl.when(pl.col("score") > 800).then(pl.lit("gold")).otherwise(pl.lit("silver")).alias("tier")
        ))
write_deltalake(table_path, v1.to_arrow(), mode="overwrite", schema_mode="overwrite")

# v2 — MERGE upsert 100K (50K updates, 50K inserts)
updates = pl.DataFrame({
    "customer_id": list(range(50_000, 150_000)),
    "status":      ["vip"] * 100_000,
    "score":       [999] * 100_000,
    "tier":        ["platinum"] * 100_000,
})
t0 = time.time()
merge_metrics = (DeltaTable(table_path)
    .merge(source=updates.to_arrow(),
           predicate="t.customer_id = s.customer_id",
           source_alias="s", target_alias="t")
    .when_matched_update_all()
    .when_not_matched_insert_all()
    .execute())
merge_seconds = time.time() - t0
print(f"MERGE 100K rows: {merge_seconds:.2f}s")
print(
    "MERGE outcome: "
    f"updated={merge_metrics['num_target_rows_updated']:,}, "
    f"inserted={merge_metrics['num_target_rows_inserted']:,}, "
    f"output={merge_metrics['num_output_rows']:,}"
)

# v3 — simulate bad data
bad = pl.DataFrame({
    "customer_id": list(range(50)),
    "status":      [None] * 50,
    "score":       [-1] * 50,
    "tier":        ["UNKNOWN"] * 50,
}, schema={"customer_id": pl.Int64, "status": pl.Utf8, "score": pl.Int64, "tier": pl.Utf8})
write_deltalake(table_path, bad.to_arrow(), mode="append")

# %% [markdown]
# ## 2. history() — audit trail

# %%
for h in DeltaTable(table_path).history():
    print(f"  v{h['version']:>2}  {h['operation']:<25}  metrics={h.get('operationMetrics', {})}")

# %% [markdown]
# ## 3. Time-travel queries

# %%
current_before_reads = DeltaTable(table_path).version()
v0_table = DeltaTable(table_path, version=0).to_pyarrow_table()
v2_table = DeltaTable(table_path, version=2).to_pyarrow_table()
v3_table = DeltaTable(table_path, version=3).to_pyarrow_table()
v0_count = v0_table.num_rows
v1_cols = DeltaTable(table_path, version=1).schema().to_arrow().names
v2_count = v2_table.num_rows
v2_bad_count = DeltaTable(table_path, version=2).to_pyarrow_table(
    filters=[("score", "<", 0)]
).num_rows
v3_count = v3_table.num_rows
v3_bad_count = DeltaTable(table_path, version=3).to_pyarrow_table(
    filters=[("score", "<", 0)]
).num_rows
current_after_reads = DeltaTable(table_path).version()
print(f"v0 row count: {v0_count}")
print(f"v1 schema:    {v1_cols}")
print(f"v2 after MERGE: rows={v2_count:,}, score<0={v2_bad_count}")
print(f"v3 bad version: rows={v3_count:,}, score<0={v3_bad_count}")
print(
    "Current version unchanged by time-travel reads: "
    f"v{current_before_reads} → v{current_after_reads}"
)

# %% [markdown]
# ## 4. RESTORE bad version (rollback)
#
# `restore(2)` rewinds the *current* state of the table to whatever it was
# at version 2, recorded as a new version (v4). The old versions stay in
# history — restore is itself a transaction, fully auditable.

# %%
t0 = time.time()
dt = DeltaTable(table_path)
restore_metrics = dt.restore(2)
restore_seconds = time.time() - t0
print(f"RESTORE → v2: {restore_seconds:.2f}s   (target < 30s)")
print(f"RESTORE metrics: {restore_metrics}")

# Verify the bad rows are gone — use delta-rs's native filter pushdown.
# (DuckDB's delta extension as of 1.5.x is stricter about post-RESTORE
# protocol entries than delta-rs writes; routing through delta-rs end-to-end
# avoids the InvalidProtocolError race.)
dt_after = DeltaTable(table_path)
bad_count = dt_after.to_pyarrow_table(filters=[("score", "<", 0)]).num_rows
restored_count = dt_after.to_pyarrow_table().num_rows
restored_version = dt_after.version()
print(f"Rows with score<0 after restore: {bad_count}  (expected 0)")
print(f"Current state after restore: version={restored_version}, rows={restored_count:,}")

# %% [markdown]
# ## 5. history() — final audit trail (now includes the RESTORE)

# %%
final_history = DeltaTable(table_path).history()
for h in final_history:
    print(f"  v{h['version']:>2}  {h['operation']:<25}")
print(f"\nTotal versions: {len(final_history)}  (target ≥ 5)")

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] history() shows ≥ 5 versions (incl. RESTORE itself)
# - [ ] MERGE 100K reports 50K updates + 50K inserts and finishes in < 60s
# - [ ] Reading old versions leaves the current version unchanged
# - [ ] v3 contains 50 bad rows; RESTORE finishes in < 30s and removes them
# - [ ] RESTORE creates a new version whose row count matches v2

# %%
ops = [h["operation"] for h in final_history]
checks = {
    "MERGE updated 50K rows":          merge_metrics["num_target_rows_updated"] == 50_000,
    "MERGE inserted 50K rows":         merge_metrics["num_target_rows_inserted"] == 50_000,
    "MERGE completed under 60s":       merge_seconds < 60,
    "bad version has 50 negative rows": v3_bad_count == 50,
    "time-travel reads are read-only": current_before_reads == current_after_reads == 3,
    "history ≥ 5 versions":          len(final_history) >= 5,
    "history includes the RESTORE":  any("RESTORE" in o.upper() for o in ops),
    "MERGE recorded in history":     any("MERGE" in o.upper() for o in ops),
    "bad rows gone after restore":   bad_count == 0,
    "restore created a new version": restored_version > 2,
    "restored row count matches v2": restored_count == v2_count,
    "RESTORE completed under 30s":   restore_seconds < 30,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB3 incomplete — see FAIL rows above"
print("\nNB3 complete.")

# %% [markdown]
# ## Nhận xét kết quả
#
# MERGE nhận 100.000 dòng nguồn: 50.000 customer_id đã tồn tại được update và 50.000
# ID mới được insert, tạo snapshot v2 gồm 150.000 dòng. Append lỗi tạo v3 với đúng 50
# dòng score < 0. Các phép đọc v0/v1/v2/v3 chỉ chọn snapshot cho reader; current
# version vẫn là v3, nên time travel là thao tác read-only và không đổi trạng thái bảng.
#
# RESTORE khác ở chỗ nó thay current state bằng snapshot logic của v2. Delta ghi việc
# đó thành transaction v4 thay vì xóa v3 để giữ lịch sử append-only, audit được ai đã
# rollback, hỗ trợ concurrency và vẫn cho phép điều tra/time travel tới trạng thái lỗi.
# Sau RESTORE, current có 150.000 dòng và score < 0 bằng 0. File cũ vẫn có thể tồn tại
# vật lý đến khi hết retention và VACUUM, nên RESTORE không phải thao tác xóa dữ liệu.
