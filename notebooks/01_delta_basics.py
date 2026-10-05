# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # NB1 — Delta Lake Basics (lightweight path)
#
# **Stack:** `deltalake` (delta-rs) + Polars + DuckDB. No Spark, no JVM.
# Maps to slide §2 (Delta Lake) + deliverable bullet 1.
#
# > Spark equivalent: `spark.read.format("delta").load(path)` ↔ `DeltaTable(path).to_pyarrow_table()`.
# > Same on-disk format, different binding.

# %%
import _setup  # noqa: F401  -- adds scripts/ to sys.path (file-relative)
import polars as pl
from deltalake import DeltaTable, write_deltalake
from lakehouse import path, reset

table_path = path("scratch", "users_delta")
reset(table_path)  # idempotent rerun

# %% [markdown]
# ## 1. Write a Delta table

# %%
df = pl.DataFrame({
    "id": [1, 2, 3],
    "name": ["alice", "bob", "charlie"],
    "age": [30, 25, 35],
    "city": ["Hanoi", "HCMC", "Danang"],
})
write_deltalake(table_path, df.to_arrow(), mode="overwrite")

# %% [markdown]
# ## 2. Read it back + inspect transaction log
#
# Look at `_lakehouse/scratch/users_delta/_delta_log/00000000000000000000.json` —
# that's the transaction log. Same JSON format Spark/Databricks would write.

# %%
dt = DeltaTable(table_path)
print(pl.from_arrow(dt.to_pyarrow_table()))
print("\nHistory:")
for h in dt.history():
    print(f"  v{h['version']}  {h['operation']}  {h.get('operationMetrics', {})}")

import json
from pathlib import Path

log_path = Path(table_path) / "_delta_log" / "00000000000000000000.json"
print(f"\n--- Contents of {log_path.name} ---")
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line)
        key = list(entry.keys())[0]
        print(f"[{key.upper()} ENTRY]:", json.dumps(entry[key], indent=2))

# %% [markdown]
# ## 3. Schema enforcement — try to write a wrong schema

# %%
bad = pl.DataFrame({"id": [4], "name": ["dan"], "age": ["thirty"], "city": ["Hue"]})
bad_blocked = False
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    bad_blocked = True
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")

# %% [markdown]
# ## 4. Schema evolution (opt-in)

# %%
new = pl.DataFrame({
    "id": [4], "name": ["dan"], "age": [28], "city": ["Hue"], "tier": ["premium"],
})
print("Schema BEFORE evolution:")
print(DeltaTable(table_path).schema())

write_deltalake(table_path, new.to_arrow(), mode="append", schema_mode="merge")
dt = DeltaTable(table_path)
print("\nSchema AFTER evolution (schema_mode='merge'):")
print(dt.schema())

# Sort by id so the printout is stable across reruns — Delta does not
# preserve write-order across appends.
print("\nTable contents after evolution:")
print(pl.from_arrow(dt.to_pyarrow_table()).sort("id"))

# %% [markdown]
# ## 5. Query with DuckDB via Arrow (part of the required notebook)

# %%
import duckdb

# We hand DuckDB an Arrow table rather than calling `delta_scan()`. delta_scan
# autoloads a DuckDB extension over the network — fine at home, a support
# ticket in a firewalled classroom. Arrow registration is zero-copy and offline.
con = duckdb.connect()
con.register("users", DeltaTable(table_path).to_pyarrow_table())
tier_counts = con.sql("SELECT tier, count(*) AS n FROM users GROUP BY 1 ORDER BY 1").fetchall()
print(tier_counts)

# %% [markdown]
# ## 📝 Báo cáo phân tích và giải thích (NB1)
#
# ### 1. Schema Enforcement khác Schema Evolution ở điểm nào?
# - **Schema Enforcement (Bảo vệ tính toàn vẹn ở tầng ghi):** Là cơ chế tự động từ chối mọi thao tác ghi dữ liệu không khớp với cấu trúc hiện tại của bảng (ví dụ: ghi giá trị string `'thirty'` vào cột `age` kiểu `int64`, hoặc thêm cột mới ngoài định nghĩa). Cơ chế này bảo vệ Lakehouse khỏi hiện tượng ô nhiễm dữ liệu ("bad data pollution"), đảm bảo các downstream pipeline (BI, ML, Dashboard) không bị gãy vỡ ngoài ý muốn.
# - **Schema Evolution (Tiến hóa cấu trúc theo thời gian):** Là cơ chế cho phép cập nhật, mở rộng schema của bảng (ví dụ: bổ sung cột `tier`) một cách có chủ đích khi nghiệp vụ thay đổi, mà không cần phải rewrite lại dữ liệu cũ hoặc recreate bảng. Các bản ghi cũ tự động nhận giá trị `null` cho cột mới bổ sung.
#
# ### 2. Vì sao việc thêm cột cần phải Opt-in?
# - Mặc định, Delta Lake áp dụng chính sách nghiêm ngặt (strict enforcement) để ngăn ngừa các writer vô tình làm sai lệch schema (schema creep/drift) do sai sót code của producer hoặc lỗi định dạng nguồn.
# - Việc thêm cột bắt buộc phải opt-in thông qua cờ tường minh (`schema_mode="merge"` trong delta-rs hoặc `.option("mergeSchema", "true")` trong Spark) nhằm xác nhận đây là một thay đổi có chủ đích từ phía kỹ sư dữ liệu, xem như một "hợp đồng giao ước" (explicit contract) bảo đảm an toàn cho các downstream consumers.
#
# ### 3. Transaction log cung cấp bằng chứng gì về một lần ghi?
# - Transaction log (`_delta_log/*.json`) là bằng chứng bất biến (immutable, append-only log) cấp ACID:
#   - **`commitInfo`:** Định danh timestamp, transaction version, operation (`WRITE`, `MERGE`, etc.), client/engine và metrics giao dịch.
#   - **`metaData`:** Ghi nhận cấu trúc schema, kiểu dữ liệu từng cột và partition keys.
#   - **`add`:** Danh sách chính xác các file Parquet mới được tạo, kèm kích thước (`size`), thời gian sửa đổi (`modificationTime`), và đặc biệt là `stats` (min/max values, nullCount, numRecords) của từng cột.
#   - **`remove`:** Danh sách các file vật lý bị tombstone (nếu có ghi đè/xóa).
# - Nhờ đó, người đọc luôn đảm bảo tính Atomicity (chỉ thấy các file đã commit trọn vẹn) và Snapshot Isolation mà không cần khóa bảng (no lock contention).

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] `_delta_log/` contains JSON files
# - [ ] Schema enforcement blocked the bad write
# - [ ] schema_mode="merge" added the `tier` column
# - [ ] DuckDB query returned 2 tier groups

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": bad_blocked,
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")
