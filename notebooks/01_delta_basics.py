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
# ### Bằng chứng: nội dung `_delta_log/` (thêm bởi học viên, chỉ đọc)

# %%
import json as _json
from pathlib import Path as _P

_log_dir = _P(table_path) / "_delta_log"
print("Files in _delta_log/:", sorted(p.name for p in _log_dir.iterdir()))
print("\nCommit 00000000000000000000.json (one action per line):")
for _line in (_log_dir / "00000000000000000000.json").read_text().splitlines():
    _action = _json.loads(_line)
    _k = next(iter(_action))
    if _k == "add":
        _a = _action["add"]
        print(f"  add: path={_a['path']}  size={_a['size']}  stats={_a['stats']}")
    elif _k == "metaData":
        print(f"  metaData: schemaString={_action['metaData']['schemaString']}")
    else:
        print(f"  {_k}: {_action[_k]}")

# %% [markdown]
# **Phân tích.** Một lần `write_deltalake` tạo đúng một file commit JSON `00000000000000000000.json`.
# File này chứa các action: `protocol` (phiên bản reader/writer), `metaData` (schema dạng JSON,
# ở đây `age` có kiểu `long`), `add` (file Parquet mới kèm stats min/max/nullCount) và `commitInfo`.
# Bảng chỉ là danh sách các file mà log nói là đang "sống". Reader replay log để biết đọc file nào.
# Đó là lý do một commit hoặc thành công toàn bộ, hoặc không xảy ra (ACID). Stats trong `add` cũng là
# thứ NB2 dùng để bỏ qua file.

# %% [markdown]
# ## 3. Schema enforcement — try to write a wrong schema

# %%
bad = pl.DataFrame({"id": [4], "name": ["dan"], "age": ["thirty"], "city": ["Hue"]})
blocked = False
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    blocked = True
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")

# Học viên thêm: chứng minh write bị chặn không để lại commit nào.
_versions = [h["version"] for h in DeltaTable(table_path).history()]
print(f"Versions after the blocked write: {_versions}  (still only v0 → nothing was committed)")
assert _versions == [0]

# %% [markdown]
# **Phân tích.** Lỗi thực tế là `Cast error: Cannot cast string 'thirty' to value of Int64 type`.
# Writer so batch mới với schema trong `metaData` của log và từ chối trước khi commit. History vẫn chỉ có v0,
# tức là không có file "rác" nào được đưa vào bảng. Nếu không có enforcement, một upstream gửi sai kiểu
# sẽ làm hỏng mọi query `AVG(age)` downstream. Data lake Parquet thuần không có cơ chế chặn này.

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
# **Phân tích schema evolution.** Cùng là thêm dữ liệu khác schema, nhưng lần này có
# `schema_mode="merge"`, tức là người ghi **chủ động opt-in**. Delta ghi commit mới với `metaData` có thêm
# cột `tier`. 3 dòng cũ đọc ra `tier = null` mà không phải rewrite file cũ nào. DuckDB thấy 2 nhóm:
# `premium` (1 dòng) và `NULL` (3 dòng). Enforcement là mặc định, evolution phải xin phép: điều này ngăn
# việc schema bị đổi âm thầm. Đây chính là failure mode F1 trong bài bonus.

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] `_delta_log/` contains JSON files
# - [ ] Schema enforcement blocked the bad write
# - [ ] schema_mode="merge" added the `tier` column
# - [ ] DuckDB query returned 2 tier groups
# The final schema-enforcement flag is hardcoded; inspect the actual error
# from the bad-write cell rather than treating that PASS line as proof.

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": blocked and _versions == [0],  # real check (was a hardcoded True)
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")
