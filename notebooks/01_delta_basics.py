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

# %% [markdown]
# ## 3. Schema enforcement — try to write a wrong schema

# %%
bad = pl.DataFrame({"id": [4], "name": ["dan"], "age": ["thirty"], "city": ["Hue"]})
schema_blocked = False
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    schema_blocked = True
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")

# %% [markdown]
# ## 4. Schema evolution (opt-in)

# %%
new = pl.DataFrame({
    "id": [4], "name": ["dan"], "age": [28], "city": ["Hue"], "tier": ["premium"],
})
write_deltalake(table_path, new.to_arrow(), mode="append", schema_mode="merge")
dt = DeltaTable(table_path)
# Sort by id so the printout is stable across reruns — Delta does not
# preserve write-order across appends.
print(pl.from_arrow(dt.to_pyarrow_table()).sort("id"))

# %% [markdown]
# ## 4.1. Bằng chứng trong transaction log và schema sau evolution
#
# Một commit Delta là tập các action JSON. Commit đầu tiên chứa `commitInfo`
# (thao tác và metrics), `protocol` (phiên bản reader/writer), `metaData`
# (schema/cấu hình bảng) và `add` (file Parquet cùng thống kê min/max/null).

# %%
import json
from pathlib import Path

log_files = sorted(Path(table_path).glob("_delta_log/*.json"))
print(f"JSON commits: {len(log_files)}")
print(f"First commit: {log_files[0].name}")
with log_files[0].open(encoding="utf-8") as fh:
    first_commit = [json.loads(line) for line in fh]
print("Action types:", [next(iter(action)) for action in first_commit])
for action in first_commit:
    if "metaData" in action:
        print("Initial schema:", action["metaData"]["schemaString"])
    if "add" in action:
        print("Added file:", action["add"]["path"])
        print("File stats:", action["add"]["stats"])

print("Schema after evolution:", DeltaTable(table_path).schema())

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
# ## ✅ Deliverable check
# - [ ] `_delta_log/` contains JSON files
# - [ ] Schema enforcement blocked the bad write
# - [ ] schema_mode="merge" added the `tier` column
# - [ ] DuckDB query returned 2 tier groups
# The final schema-enforcement flag is hardcoded; inspect the actual error
# from the bad-write cell; `schema_blocked` below is set only in the exception path.

# %% [markdown]
# ## Giải thích kết quả
#
# **Schema enforcement** giữ nguyên hợp đồng hiện tại và từ chối dữ liệu không
# tương thích, như chuỗi `"thirty"` ghi vào cột `age: Int64`. **Schema evolution**
# thay đổi hợp đồng một cách có chủ ý; ở đây `schema_mode="merge"` cho phép thêm
# cột `tier`, còn các dòng cũ nhận giá trị `NULL`.
#
# Việc thêm cột cần opt-in để lỗi chính tả, producer sai phiên bản hoặc thay đổi
# ngoài dự kiến không âm thầm làm biến dạng schema dùng chung. Người ghi phải
# thể hiện rõ ý định thay đổi hợp đồng dữ liệu.
#
# Transaction log cung cấp audit trail của lần ghi: loại operation và metrics,
# protocol, schema/cấu hình tại thời điểm commit, file Parquet được thêm và thống
# kê của file. Vì các action được commit nguyên tử, reader thấy toàn bộ phiên bản
# mới hoặc phiên bản cũ, không thấy trạng thái ghi dở dang.

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": schema_blocked,
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")
