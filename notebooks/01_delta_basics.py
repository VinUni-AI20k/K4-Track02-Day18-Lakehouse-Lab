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
# ### 2b. Evidence: list `_delta_log/` and print the first commit JSON
#
# Each line of the commit is one action: `commitInfo`, `protocol`, `metaData`
# (schema as JSON string) and one `add` per data file (with per-file stats).

# %%
import json
from pathlib import Path

log_dir = Path(table_path) / "_delta_log"
print("Files in _delta_log/:", sorted(p.name for p in log_dir.iterdir()))
print()
with open(log_dir / "00000000000000000000.json", encoding="utf-8") as fh:
    for line in fh:
        action = json.loads(line)
        kind = next(iter(action))
        body = json.dumps(action[kind], ensure_ascii=False)
        print(f"{kind:<10} {body[:220]}{' ...' if len(body) > 220 else ''}")

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
# A blocked write must not leave a commit behind.
version_after_bad = DeltaTable(table_path).version()
print(f"Table version before/after bad write: {version_before_bad} / {version_after_bad}")

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
# The schema-enforcement flag is now set by the bad-write cell itself
# (exception raised AND no new commit), instead of a hardcoded True.

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
# ## 📝 Giải thích kết quả NB1
#
# - **Transaction log.** `_delta_log/00000000000000000000.json` là commit đầu tiên; mỗi dòng là một *action*:
#   `commitInfo` (thao tác gì, khi nào, engine nào), `protocol` (reader v1 / writer v2), `metaData` (schema dạng JSON string)
#   và `add` cho từng file Parquet kèm `stats` (numRecords, min/max mỗi cột). Bảng = Parquet + log; trạng thái hiện tại
#   là kết quả replay các action. Sau bước evolution, log có 2 commit JSON (v0 WRITE, v1 WRITE với schema merge).
# - **Schema enforcement.** Ghi `age='thirty'` bị chặn với `Cast error: Cannot cast string 'thirty' to value of Int64 type`.
#   Bằng chứng không chỉ là thông báo lỗi: version trước/sau lần ghi lỗi đều là `0` → không có commit nào được tạo,
#   không có file rác được tham chiếu. (Cờ PASS cuối notebook bản gốc bị hardcode `True`; mình đã sửa để nó lấy từ
#   chính exception và việc version không đổi.)
# - **Schema evolution là opt-in.** Chỉ khi truyền `schema_mode="merge"` thì cột `tier` mới được thêm; 3 dòng cũ đọc ra
#   `tier = null` mà không phải rewrite file cũ — schema mới chỉ nằm trong `metaData` của commit v1.
# - **DuckDB** thấy 2 nhóm tier: `premium` (1 dòng) và `NULL` (3 dòng) — nhóm NULL chính là các dòng ghi trước evolution.
