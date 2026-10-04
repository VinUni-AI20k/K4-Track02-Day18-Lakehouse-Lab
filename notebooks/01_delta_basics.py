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
bad_write_blocked = False
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    bad_write_blocked = True
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
# The schema-enforcement flag is set by the except branch of the bad-write
# cell, and the history check proves the rejected write left no commit.

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": bad_write_blocked,
    "table unchanged by bad write (3 rows before merge)": DeltaTable(table_path, version=0).to_pyarrow_table().num_rows == 3
        and len(DeltaTable(table_path).history()) == 2,
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")

# %% [markdown]
# ## 📝 Phân tích kết quả (NB1)
#
# - **Transaction log:** sau 2 lần ghi thành công có 2 commit JSON (`00000000000000000000.json`, `...01.json`)
#   trong `_lakehouse/scratch/users_delta/_delta_log/`. Mỗi commit liệt kê action `add` (file Parquet + stats
#   min/max) và `metaData`/`protocol`. Bảng = Parquet + log; reader chỉ thấy file mà log tham chiếu, nên một lần
#   ghi hoặc thành công trọn vẹn hoặc không để lại gì (ACID).
# - **Schema enforcement:** ghi `age="thirty"` bị từ chối với lỗi thật `Cast error: Cannot cast string 'thirty'
#   to value of Int64 type`. Check cuối không còn hardcode `True`: cờ `bad_write_blocked` chỉ bật trong nhánh
#   `except`, và `history()` chỉ có 2 version → lần ghi lỗi **không để lại commit nào**.
# - **Schema evolution là opt-in:** `schema_mode="merge"` thêm cột `tier`; 3 dòng cũ đọc ra `tier = null`
#   mà không cần rewrite file cũ. DuckDB thấy đúng 2 nhóm: `premium` (1) và `NULL` (3).
# - **Ý nghĩa:** enforcement mặc định chặn dữ liệu bẩn ở ranh giới ghi; muốn đổi schema phải khai báo rõ — đó là
#   khác biệt giữa lakehouse và một thư mục Parquet "data swamp".

# %% [markdown]
# ## ❓ Trả lời câu hỏi (mục 3.1)
#
# **1. Enforcement khác evolution ở điểm nào?**
# Enforcement là hành vi *mặc định*: mọi lần ghi phải khớp schema đã có trong log; lần ghi `age="thirty"` (string
# vào cột Int64) bị từ chối toàn bộ (`Cast error: Cannot cast string 'thirty' to value of Int64 type`) và không tạo
# commit nào — `history()` vẫn chỉ có các commit hợp lệ. Evolution là thay đổi schema *có chủ đích*: chỉ xảy ra khi
# người ghi bật `schema_mode="merge"`; khi đó cột `tier` được thêm vào `metaData.schemaString` và dòng cũ đọc ra NULL.
# Enforcement bảo vệ dữ liệu khỏi sai kiểu; evolution cho phép schema lớn dần nhưng có kiểm soát.
#
# **2. Vì sao thêm cột cần opt-in?**
# Nếu bảng tự nhận mọi cột mới, một producer gõ sai tên cột (`teir`), đổi kiểu, hoặc gửi payload rác sẽ âm thầm
# làm thay đổi schema mà mọi consumer downstream (dashboard, job Silver/Gold) phải gánh. Bắt opt-in biến thay đổi
# schema thành một quyết định có chủ ý, được ghi lại trong log, thay vì một tác dụng phụ của một lần ghi.
#
# **3. Transaction log cung cấp bằng chứng gì về một lần ghi?**
# Commit `00000000000000000001.json` (ảnh `nb01_delta_log.png`) ghi: `commitInfo` (thời điểm, `operation: WRITE`,
# `mode: Append`, engine `delta-rs:py-1.6.6`, `num_added_rows: 1`), `metaData` (schema mới có `tier`), và action
# `add` với đường dẫn file Parquet, kích thước, `dataChange: true` và stats `numRecords`/min/max từng cột.
# Tức là log trả lời được *ai/khi nào/thao tác gì/những file nào thuộc version này* — đó là nền cho ACID, time travel
# và file skipping. Ghi chú: cờ enforcement ở cuối notebook gốc bị hardcode `True`; mình đã thay bằng cờ thật
# `bad_write_blocked` lấy từ nhánh `except` của cell ghi sai kiểu.
