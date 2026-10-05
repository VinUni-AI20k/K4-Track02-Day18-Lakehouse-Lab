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
# A blocked write must not leave a commit behind: the version stays the same.
bad_write_blocked = bad_write_blocked and DeltaTable(table_path).version() == version_before_bad
print(f"Table version before/after the bad write: {version_before_bad} → {DeltaTable(table_path).version()}")

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
# ## 6. Evidence: the `_delta_log/` commits on disk
#
# Added for the submission: list the JSON commits and show what each one
# records. v0 carries `protocol` + `metaData` (schema) + `add`; the schema-merge
# commit carries a new `metaData` whose schema now includes `tier`.

# %%
import json  # noqa: E402
from pathlib import Path as _P  # noqa: E402

log_dir = _P(table_path) / "_delta_log"
for f in sorted(log_dir.glob("*.json")):
    actions = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    print(f"{f.name}  ({f.stat().st_size} B)  actions={[next(iter(a)) for a in actions]}")

print("\n--- 00000000000000000000.json (first commit) ---")
for line in (log_dir / "00000000000000000000.json").read_text().splitlines():
    a = json.loads(line)
    kind = next(iter(a))
    if kind == "metaData":
        fields = json.loads(a["metaData"]["schemaString"])["fields"]
        print("metaData.schema:", [(fl["name"], fl["type"]) for fl in fields])
    elif kind == "add":
        print("add:", {k: a["add"][k] for k in ("path", "size", "dataChange")})
        print("add.stats:", a["add"]["stats"])
    else:
        print(f"{kind}:", a[kind])

last_commit = sorted(log_dir.glob("*.json"))[-1]
for line in last_commit.read_text().splitlines():
    a = json.loads(line)
    if "metaData" in a:
        fields = json.loads(a["metaData"]["schemaString"])["fields"]
        print(f"\n{last_commit.name} metaData.schema:", [(fl["name"], fl["type"]) for fl in fields])

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] `_delta_log/` contains JSON files
# - [ ] Schema enforcement blocked the bad write
# - [ ] schema_mode="merge" added the `tier` column
# - [ ] DuckDB query returned 2 tier groups
# The schema-enforcement flag is set by the bad-write cell: True only if the
# write raised AND the table version did not move.

# %%
from pathlib import Path as _Path  # noqa: E402

_log = sorted(_Path(table_path).glob("_delta_log/*.json"))
_cols = DeltaTable(table_path).schema().to_arrow().names
checks = {
    "_delta_log/ has JSON commits": len(_log) >= 2,
    "schema enforcement blocked bad write": bad_write_blocked,
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")
