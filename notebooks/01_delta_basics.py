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
version_before_bad = DeltaTable(table_path).version()
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    bad_write_blocked = False
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    bad_write_blocked = True
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")
# A blocked write must not create a commit: the table version is unchanged.
version_after_bad = DeltaTable(table_path).version()
print(f"Table version before/after the bad write: v{version_before_bad} → v{version_after_bad}")

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
# ## 4b. Evidence — `_delta_log/` after two commits
#
# List the commit files and print the actions inside the second commit
# (the schema-merge append). Each line of a commit JSON is one action.

# %%
import json
from pathlib import Path as _P

log_files = sorted(_P(table_path).glob("_delta_log/*.json"))
for f in log_files:
    print(f"  {f.name}  ({f.stat().st_size} B)")

print()
print(f"Actions in {log_files[-1].name}:")
for line in log_files[-1].read_text(encoding="utf-8").splitlines():
    action = json.loads(line)
    kind = next(iter(action))
    body = action[kind]
    if kind == "metaData":
        fields = [fld["name"] for fld in json.loads(body["schemaString"])["fields"]]
        print(f"  metaData  → schema fields = {fields}")
    elif kind == "add":
        print(f"  add       → {body['path'][:60]}  size={body['size']} B  stats={body.get('stats')}")
    elif kind == "commitInfo":
        print(f"  commitInfo→ operation={body.get('operation')}  params={body.get('operationParameters')}")
    else:
        print(f"  {kind:<9} → {json.dumps(body)[:100]}")

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
# The schema-enforcement flag below is set by the bad-write cell itself
# (originally a hardcoded `True`), and it also requires that the blocked
# write did not create a new table version.

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": bad_write_blocked and version_after_bad == version_before_bad,
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")

# %% [markdown]
# ## Giải thích kết quả (NB1)
#
# * **Transaction log.** Sau hai lần ghi thành công, `_delta_log/` có đúng hai commit
#   `00000000000000000000.json` (v0 — `WRITE`, 3 dòng) và `00000000000000000001.json`
#   (v1 — append có `schema_mode="merge"`). Mỗi dòng trong commit là một *action*.
#   Commit v1 in ở trên có 3 action: `commitInfo` (operation `WRITE`, mode `Append`),
#   `metaData` (schema mới 5 field, đã có `tier`) và `add` (file Parquet mới kèm `stats`:
#   numRecords, min/max, nullCount theo cột — chính là dữ liệu NB2 dùng để skip file).
#   Bảng Delta = thư mục Parquet + log này; reader dựng lại trạng thái hiện tại bằng
#   cách replay các action theo thứ tự version.
# * **Schema enforcement.** Ghi `age="thirty"` vào cột `Int64` bị chặn ngay khi writer
#   cast dữ liệu (`Cannot cast string 'thirty' to value of Int64 type`). Quan trọng hơn
#   dòng PASS: version bảng **không đổi** sau lần ghi lỗi (v0 → v0), tức không có commit
#   nửa vời nào — đó là tính *atomic* của ACID. Cờ kiểm tra cuối notebook giờ lấy từ
#   chính cell này thay cho giá trị `True` hardcode trong bản gốc.
# * **Schema evolution là opt-in.** Chỉ khi truyền `schema_mode="merge"` thì cột `tier`
#   mới được thêm vào `metaData` của commit v1. Ba dòng cũ không bị rewrite — đọc lên
#   với `tier = null`, nên DuckDB thấy 2 nhóm: `premium` (1) và `NULL` (3).
#   Nếu không opt-in, cùng lần ghi đó sẽ bị từ chối như lần ghi sai kiểu.
