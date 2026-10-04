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
try:
    write_deltalake(table_path, bad.to_arrow(), mode="append")
    print("UNEXPECTED: bad write succeeded — schema enforcement broken")
except Exception as e:
    msg = str(e).splitlines()[0][:120]
    print(f"BLOCKED by schema enforcement (expected): {type(e).__name__}: {msg}")

# %% [markdown]
# ### 🔎 Bằng chứng bổ sung — lần ghi sai kiểu có để lại commit nào không?
#
# *(Cell do học viên thêm, chỉ đọc.)* Cờ enforcement ở cuối notebook đang hardcoded,
# nên kiểm tra trực tiếp: nếu bad write bị chặn thật thì bảng vẫn ở version 0,
# vẫn 3 dòng và `_delta_log/` chỉ có đúng 1 commit.

# %%
from pathlib import Path

_dt = DeltaTable(table_path)
_commits = sorted(p.name for p in (Path(table_path) / "_delta_log").glob("*.json"))
print(f"version sau lần ghi lỗi : {_dt.version()}")
print(f"số dòng                 : {_dt.count()}")
print(f"commit JSON trong log   : {_commits}")
print(f"kiểu cột age            : {_dt.schema().to_arrow().field('age').type}")
assert _dt.version() == 0 and _dt.count() == 3, "bad write đã lọt vào bảng!"
print("→ Không có commit mới: lần ghi bị từ chối trọn vẹn, bảng không đổi.")

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
# ### 🔎 Bằng chứng bổ sung — schema mới và nội dung transaction log
#
# *(Cell do học viên thêm, chỉ đọc.)* In schema sau evolution và từng action
# trong mỗi commit JSON (rút gọn `add`/`metaData`/`commitInfo` cho dễ đọc).

# %%
import json

print("Schema sau evolution:")
print(DeltaTable(table_path).schema())

log_dir = Path(table_path) / "_delta_log"
print("\nFiles trong _delta_log/:")
for f in sorted(log_dir.iterdir()):
    print(f"  {f.name:<28} {f.stat().st_size:>6} B")

for f in sorted(log_dir.glob("*.json")):
    print(f"\n── {f.name} ──")
    for line in f.read_text(encoding="utf-8").splitlines():
        kind, body = next(iter(json.loads(line).items()))
        if kind == "add":
            body = {k: body.get(k) for k in ("path", "size", "dataChange", "stats")}
        elif kind == "metaData":
            fields = json.loads(body["schemaString"])["fields"]
            body = {"schema": [f"{x['name']}:{x['type']}" for x in fields],
                    "partitionColumns": body.get("partitionColumns")}
        elif kind == "commitInfo":
            body = {k: body.get(k) for k in ("timestamp", "operation", "operationParameters", "clientVersion")}
        print(f"  {kind:<10} {json.dumps(body, ensure_ascii=False)}")

# %% [markdown]
# ### 🔎 Thí nghiệm thêm — enforcement của delta-rs là "cast được thì ghi"
#
# *(Cell do học viên thêm.)* Ghi thử nhiều kiểu sai trên một bảng scratch **riêng**
# (`users_cast_probe`) để không ảnh hưởng bảng chính và các check bên dưới.

# %%
probe = path("scratch", "users_cast_probe")
reset(probe)
write_deltalake(probe, pl.DataFrame({"id": [1], "age": [30]}).to_arrow(), mode="overwrite")
for label, frame in [
    ("age='thirty' (str)", pl.DataFrame({"id": [2], "age": ["thirty"]})),
    ("age='31' (str)",     pl.DataFrame({"id": [3], "age": ["31"]})),
    ("age=1.5 (float)",    pl.DataFrame({"id": [4], "age": [1.5]})),
    ("thêm cột 'extra'",   pl.DataFrame({"id": [5], "age": [40], "extra": ["x"]})),
]:
    try:
        write_deltalake(probe, frame.to_arrow(), mode="append")
        result = "GHI ĐƯỢC"
    except Exception as e:
        result = f"BỊ CHẶN ({type(e).__name__})"
    print(f"  {label:<20} → {result}")
print("\nDữ liệu cuối cùng trong bảng probe:")
print(pl.from_arrow(DeltaTable(probe).to_pyarrow_table()).sort("id"))

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
# ## 📝 Giải thích kết quả NB1 (Lò Văn Long — 2A202602541)
#
# **Số đo trên máy mình** (Windows 10, Python 3.11.9, `deltalake` 1.6.6):
#
# | Kiểm tra | Kết quả | Ngưỡng |
# |---|---|---|
# | Commit JSON trong `_delta_log/` | 2 (`…000.json` WRITE overwrite, `…001.json` WRITE append) | ≥ 2 |
# | Ghi `age='thirty'` | Bị chặn: `Cast error: Cannot cast string 'thirty' to value of Int64 type`; bảng vẫn **version 0, 3 dòng, 1 commit** | bị chặn |
# | `schema_mode="merge"` | Schema thành `id, name, age, city, tier`; 3 dòng cũ có `tier = null` | có cột `tier` |
# | DuckDB `GROUP BY tier` | `[('premium', 1), (None, 3)]` → 2 nhóm | 2 nhóm |
#
# **Enforcement khác evolution ở đâu?**
# - *Enforcement* là kiểm tra lúc **ghi**: delta-rs đối chiếu dữ liệu mới với schema đang nằm trong action
#   `metaData` của log. Không khớp thì cả transaction bị từ chối, không có file nào được commit. Cell bằng
#   chứng cho thấy bảng vẫn ở version 0 sau lần ghi lỗi, tức là lỗi xảy ra trước khi commit.
# - *Evolution* là **đổi chính schema của bảng**. Lần append có `schema_mode="merge"` ghi một action
#   `metaData` mới (thấy trong `…001.json`, schema có thêm `tier:string`). Các file Parquet cũ không bị
#   viết lại; reader tự điền `null` cho cột mới.
# - Thí nghiệm thêm cho thấy enforcement của delta-rs 1.6.6 là **"ép kiểu được thì ghi"**, không phải so
#   kiểu tuyệt đối. `'31'` (string) được ép thành `31`; `1.5` (float) bị **cắt thành `1`** mà không báo lỗi.
#   Chỉ `'thirty'` (không ép được) và cột lạ `extra` (sai số cột) bị chặn. Vì vậy enforcement không thay
#   được data-quality check ở tầng Silver, ví dụ kiểm tra kiểu nguồn hoặc khoảng giá trị.
#
# **Vì sao thêm cột cần opt-in?** Schema là hợp đồng với mọi reader phía sau (dashboard, job ML, BI).
# Nếu writer tự thêm cột, một lỗi gõ (`custmer_id`) hay việc upstream đổi format sẽ âm thầm làm bảng phình
# ra và làm hỏng các truy vấn phía sau mà không ai được báo. Bắt buộc `schema_mode="merge"` khiến thay đổi
# schema thành một quyết định có chủ đích, và quyết định đó được ghi lại trong log.
#
# **Transaction log cho bằng chứng gì về một lần ghi?** Mỗi commit là một file JSON đánh số liên tiếp, gồm:
# `commitInfo` (thời điểm, operation `WRITE`, mode `Overwrite`/`Append`, client `delta-rs.py-1.6.6`),
# `protocol` (reader/writer version tối thiểu), `metaData` (schema, partition) và `add` cho từng file
# Parquet (path, size, `dataChange` và **stats** `numRecords`/`minValues`/`maxValues`/`nullCount`).
# Từ đó biết chính xác version nào gồm những file nào (time travel), ai ghi gì và lúc nào (audit). Stats
# min/max cũng là nền tảng cho file skipping ở NB2. Reader chỉ thấy các file đã được `add` trong log, nên
# một lần ghi hỏng giữa chừng sẽ không lộ ra ngoài.

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
    "schema enforcement blocked bad write": True,   # placeholder; inspect the bad-write output
    "tier column added via schema_mode=merge": "tier" in _cols,
    "duckdb sees 2 tier groups": len(tier_counts) == 2,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB1 incomplete — see FAIL rows above"
print("\nNB1 complete.")
