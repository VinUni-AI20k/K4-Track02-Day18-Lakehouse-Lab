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

# %%
# Evidence: list `_delta_log/` and print the actions inside commit v0.
import json
from pathlib import Path

log_dir = Path(table_path) / "_delta_log"
print(f"{log_dir}:")
for f in sorted(log_dir.iterdir()):
    print(f"  {f.name:<32} {f.stat().st_size:>6} B")

print("\n00000000000000000000.json — one JSON action per line:")
for line in (log_dir / "00000000000000000000.json").read_text().splitlines():
    action = json.loads(line)
    print(json.dumps(action, indent=2)[:900])

# %% [markdown]
# ## 3. Schema enforcement — try to write a wrong schema

# %%
bad = pl.DataFrame({"id": [4], "name": ["dan"], "age": ["thirty"], "city": ["Hue"]})
version_before_bad = DeltaTable(table_path).version()
bad_write_blocked = False
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    bad_write_blocked = True
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")
version_after_bad = DeltaTable(table_path).version()
print(f"Table version before/after the rejected write: v{version_before_bad} → v{version_after_bad}"
      "  (no new commit)")

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

# %%
# Evidence: the opt-in evolution is itself a commit. v1 carries a new
# `metaData` action whose schema now includes `tier`.
print(f"{log_dir}:")
for f in sorted(log_dir.iterdir()):
    print(f"  {f.name:<32} {f.stat().st_size:>6} B")

for line in (log_dir / "00000000000000000001.json").read_text().splitlines():
    action = json.loads(line)
    kind = next(iter(action))
    if kind == "metaData":
        fields = [f["name"] for f in json.loads(action["metaData"]["schemaString"])["fields"]]
        print(f"\nv1 metaData schema fields: {fields}")
    elif kind == "commitInfo":
        print(f"v1 commitInfo: operation={action[kind]['operation']}  "
              f"params={action[kind].get('operationParameters')}")

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
# The schema-enforcement flag is set inside the bad-write `except` block and
# also requires that the rejected write created no new table version.

# %%
_log = sorted(Path(table_path).glob("_delta_log/*.json"))
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
