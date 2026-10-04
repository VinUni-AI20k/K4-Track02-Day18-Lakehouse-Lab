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

# %% [markdown]
# ## 📝 Phân tích kết quả (NB3)
#
# - **MERGE 100K dòng:** metrics trong `history()` ghi `num_target_rows_updated=50000`,
#   `num_target_rows_inserted=50000`, `num_output_rows=150000` — đúng thiết kế (50K key trùng → update, 50K mới
#   → insert), chạy dưới 1 giây trên đường lightweight.
# - **Time travel:** `version=0` vẫn đọc được 100,000 dòng; `version=1` có schema thêm `tier`. Đọc version cũ
#   chỉ là đọc lại tập file mà log ở version đó tham chiếu.
# - **RESTORE:** v3 chèn 50 dòng `score=-1`. `restore(2)` tạo **commit mới v4 (RESTORE)** thay vì xóa lịch sử,
#   nên `history()` có **5 version** (WRITE, WRITE, MERGE, WRITE, RESTORE) và số dòng `score < 0` = **0**.
# - **Ý nghĩa:** rollback là một transaction có audit trail — vẫn biết dữ liệu lỗi vào ở v3 và được gỡ ở v4.
#   Chừng nào chưa VACUUM, file chứa dữ liệu lỗi vẫn nằm trên đĩa (xem NB6, NB8).

# %% [markdown]
# ## ❓ Trả lời câu hỏi (mục 3.3)
#
# **1. Đọc version cũ khác RESTORE thế nào?**
# `DeltaTable(path, version=0)` là thao tác *chỉ đọc*: dựng lại tập file mà log ở v0 tham chiếu (100,000 dòng) và
# không thay đổi bảng — version hiện tại vẫn là bản mới nhất, người khác đọc bảng không bị ảnh hưởng. `restore(2)`
# là thao tác *ghi*: nó tạo commit mới (v4, operation `RESTORE`) gồm action `remove` cho file được thêm sau v2 (file chứa
# 50 dòng `score=-1`) và `add` lại file của v2, nên từ đó mọi reader thấy trạng thái v2 (0 dòng `score < 0`).
#
# **2. Vì sao RESTORE tạo transaction mới thay vì xóa lịch sử?**
# - *Log chỉ ghi thêm (append-only):* xóa commit v3 sẽ phá tính nhất quán cho reader/writer đang dùng các version đó
#   và mâu thuẫn với optimistic concurrency của Delta.
# - *Audit:* history cuối vẫn cho thấy WRITE (v3, dữ liệu lỗi) rồi RESTORE (v4) — biết lỗi vào lúc nào và được
#   gỡ lúc nào, phục vụ điều tra sự cố.
# - *Có thể đảo ngược:* nếu restore nhầm, vẫn có thể time travel/restore tới v3.
# Hệ quả: file chứa dữ liệu lỗi vẫn nằm trên đĩa cho tới khi VACUUM vượt retention (NB6).
