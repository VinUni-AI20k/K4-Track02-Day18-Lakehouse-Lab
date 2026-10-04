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
(DeltaTable(table_path)
    .merge(source=updates.to_arrow(),
           predicate="t.customer_id = s.customer_id",
           source_alias="s", target_alias="t")
    .when_matched_update_all()
    .when_not_matched_insert_all()
    .execute())
print(f"MERGE 100K rows: {time.time()-t0:.2f}s")

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
v0_count = DeltaTable(table_path, version=0).to_pyarrow_table().num_rows
v1_cols  = DeltaTable(table_path, version=1).schema().to_arrow().names
print(f"v0 row count: {v0_count}")
print(f"v1 schema:    {v1_cols}")

# %% [markdown]
# ## 4. RESTORE bad version (rollback)
#
# `restore(2)` rewinds the *current* state of the table to whatever it was
# at version 2, recorded as a new version (v4). The old versions stay in
# history — restore is itself a transaction, fully auditable.

# %%
t0 = time.time()
dt = DeltaTable(table_path)
dt.restore(2)
print(f"RESTORE → v2: {time.time()-t0:.2f}s   (target < 30s)")

# Verify the bad rows are gone — use delta-rs's native filter pushdown.
# (DuckDB's delta extension as of 1.5.x is stricter about post-RESTORE
# protocol entries than delta-rs writes; routing through delta-rs end-to-end
# avoids the InvalidProtocolError race.)
dt_after = DeltaTable(table_path)
bad_count = dt_after.to_pyarrow_table(filters=[("score", "<", 0)]).num_rows
print(f"Rows with score<0 after restore: {bad_count}  (expected 0)")

# %% [markdown]
# ## 5. history() — final audit trail (now includes the RESTORE)

# %%
final_history = DeltaTable(table_path).history()
for h in final_history:
    print(f"  v{h['version']:>2}  {h['operation']:<25}")
print(f"\nTotal versions: {len(final_history)}  (target ≥ 5)")

# %% [markdown]
# ### 🔎 Bằng chứng bổ sung — từng version còn đọc được, kể cả version lỗi
#
# *(Cell do học viên thêm, chỉ đọc.)* Sau RESTORE, version hiện tại sạch nhưng v3 (có dữ liệu lỗi)
# vẫn truy vấn được bằng time travel: RESTORE không xóa lịch sử.

# %%
for v in range(len(final_history)):
    t = DeltaTable(table_path, version=v)
    neg = t.to_pyarrow_table(filters=[("score", "<", 0)]).num_rows
    print(f"  v{v}: rows={t.count():>7,}  score<0={neg:>3}  columns={t.schema().to_arrow().names}")

# %% [markdown]
# ## 📝 Giải thích kết quả NB3 (Lò Văn Long — 2A202602541)
#
# **Lịch sử version đo được:**
#
# | Version | Operation | Kết quả |
# |---|---|---|
# | v0 | WRITE (overwrite) | 100.000 khách hàng |
# | v1 | WRITE (overwrite + `schema_mode="overwrite"`) | thêm cột `tier`, ghi lại toàn bộ 100.000 dòng (1 file thêm, 1 file bỏ) |
# | v2 | **MERGE** 100K dòng nguồn | `num_target_rows_updated = 50.000` (id 50K–99.999), `inserted = 50.000` (id 100K–149.999), `copied = 50.000` → 150.000 dòng; chạy dưới 0,1 giây |
# | v3 | WRITE (append) | 50 dòng lỗi `score = -1`, `status = null`, `tier = 'UNKNOWN'` → 150.050 dòng |
# | v4 | **RESTORE** về v2 | 150.000 dòng, `score < 0` = **0**; chạy khoảng 0,01–0,02 giây (< 30 giây) |
#
# `history()` có **5 version gồm cả dòng RESTORE**, đạt ngưỡng ≥ 5.
#
# **Đọc version cũ khác RESTORE thế nào?**
# - `DeltaTable(path, version=N)` (tương đương `versionAsOf`) là thao tác **chỉ đọc**. Nó dựng lại trạng thái
#   tại v3 từ log để truy vấn (cell bằng chứng: v3 vẫn có 50 dòng `score < 0`). Bảng hiện tại không đổi và
#   reader khác vẫn thấy version mới nhất.
# - `restore(2)` là thao tác **ghi**. Nó tạo commit mới v4: `add` lại các file thuộc v2 và `remove` file
#   chứa 50 dòng lỗi của v3. Từ v4 trở đi, mọi reader mặc định đều thấy dữ liệu sạch.
#
# **Vì sao RESTORE tạo transaction mới thay vì xóa lịch sử?**
# 1. Log của Delta **chỉ được append, không sửa** (immutable). Version là số tăng dần mà cơ chế optimistic
#    concurrency dựa vào. Xóa hay sửa commit cũ sẽ làm hỏng reader hoặc writer đang chạy ở version đó.
# 2. **Kiểm toán:** v4 ghi rõ có người đã rollback, lúc nào và về đâu. Sự cố v3 vẫn còn để điều tra nguyên
#    nhân, ví dụ job nào ghi `score = -1`.
# 3. **Có thể hoàn tác chính lần RESTORE:** nếu rollback nhầm thì vẫn restore về v3 được.
#
# **Lưu ý vận hành:** RESTORE chỉ chạy được khi file Parquet của version đích còn trên đĩa. Sau khi
# `VACUUM` xóa file đã hết retention (NB6), cả time travel lẫn RESTORE về các version đó đều thất bại. Ngoài
# ra, v1 ở lab thêm cột bằng cách overwrite toàn bảng. Ở production nên dùng `schema_mode="merge"` hoặc
# `ALTER TABLE ADD COLUMNS` (chỉ đổi metadata) để không phải ghi lại 100% dữ liệu.

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] history() shows ≥ 5 versions (incl. RESTORE itself)
# - [ ] MERGE 100K finished in < 60s (likely < 1s on lightweight path)
# - [ ] RESTORE finished in < 30s and removed bad rows

# %%
ops = [h["operation"] for h in final_history]
checks = {
    "history ≥ 5 versions":          len(final_history) >= 5,
    "history includes the RESTORE":  any("RESTORE" in o.upper() for o in ops),
    "MERGE recorded in history":     any("MERGE" in o.upper() for o in ops),
    "bad rows gone after restore":   bad_count == 0,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB3 incomplete — see FAIL rows above"
print("\nNB3 complete.")
