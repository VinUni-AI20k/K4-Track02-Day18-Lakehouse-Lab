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
import json
from pathlib import Path

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

log_files = sorted(Path(table_path).glob("_delta_log/*.json"))
print("\n_delta_log JSON commits:")
for commit in log_files:
    print(f"  {commit.name}")
print(f"\nFirst commit content ({log_files[0].name}):")
commit_lines = log_files[0].read_text(encoding="utf-8").splitlines()
for line in commit_lines:
    print(f"  {line}")
print("Action types:", [next(iter(json.loads(line))) for line in commit_lines])

# %% [markdown]
# ## 3. Schema enforcement — try to write a wrong schema

# %%
bad = pl.DataFrame({"id": [4], "name": ["dan"], "age": ["thirty"], "city": ["Hue"]})
version_before_bad_write = DeltaTable(table_path).version()
schema_enforcement_blocked = False
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    schema_enforcement_blocked = True
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")
bad_write_version_unchanged = DeltaTable(table_path).version() == version_before_bad_write
print(f"Version unchanged after rejected write: {bad_write_version_unchanged}")

# %% [markdown]
# ## 4. Schema evolution (opt-in)

# %%
new = pl.DataFrame({
    "id": [4], "name": ["dan"], "age": [28], "city": ["Hue"], "tier": ["premium"],
})
write_deltalake(table_path, new.to_arrow(), mode="append", schema_mode="merge")
dt = DeltaTable(table_path)
print("Evolved schema:")
print(dt.schema())
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
print("Tier groups:", tier_counts)

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] `_delta_log/` contains JSON files
# - [ ] Schema enforcement blocked the bad write
# - [ ] schema_mode="merge" added the `tier` column
# - [ ] DuckDB query returned 2 tier groups
# The check below uses the exception observed in the bad-write cell.

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
print("Final _delta_log commits:", [commit.name for commit in _log])
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": schema_enforcement_blocked,
    "rejected write created no commit": bad_write_version_unchanged,
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees expected 2 tier groups": set(tier_counts) == {(None, 3), ("premium", 1)},
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")

# %% [markdown]
# ## Nhận xét kết quả
#
# Schema enforcement kiểm tra dữ liệu mới theo schema hiện tại: age="thirty" không
# thể ép sang Int64 nên bị từ chối, version không đổi và không có commit rác. Schema
# evolution thay đổi schema có chủ đích; schema_mode="merge" là opt-in để một writer
# không vô tình làm drift schema và phá reader downstream. Sau evolution, tier xuất
# hiện; ba dòng cũ nhận NULL, dòng mới nhận premium và DuckDB thấy đúng hai nhóm.
#
# Transaction log là bằng chứng versioned của lần ghi: commitInfo ghi operation và
# metrics, protocol ghi hợp đồng reader/writer, metaData ghi schema, còn add trỏ đến
# file Parquet cùng statistics. Hai file JSON tương ứng hai transaction thành công;
# lần ghi sai kiểu không tạo version mới. Nhờ đó reader tái dựng snapshot nhất quán
# và audit được dữ liệu vật lý nào thuộc mỗi version.
