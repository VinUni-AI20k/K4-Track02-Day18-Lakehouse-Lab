# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # NB5 — Apache Iceberg & the Catalog as Control Plane
#
# **Stack:** `pyiceberg` + a local SQLite catalog. No JVM, no server, no cloud.
# Maps to slide §4 (Apache Iceberg) + §12 (Catalog = Control Plane) + deliverable bullet 5.
#
# NB1–NB4 used Delta. Here you meet the *other* open table format — and more
# importantly, the thing both formats now agree is the centre of the
# architecture: **the catalog**.
#
# > **Catalog responsibilities.** This notebook uses a local SQLite catalog
# > for namespaces, table registration and metadata updates. It demonstrates
# > client-side scan planning, not remote planning or a security boundary.
#
# > Production equivalent: `SqlCatalog(sqlite)` ↔ `load_catalog(type="rest")`
# > against a compatible REST catalog. Production catalogs require separate
# > configuration, authentication and checking which APIs/features they support.

# %%
import _setup  # noqa: F401  -- adds scripts/ to sys.path (file-relative)

import datetime as dtm

import pyarrow as pa

from lakehouse import catalog, count_files, du, human, namespace, reset_catalog

CAT = "nb5"          # own catalog dir: NB6/NB8/`make smoke` cannot disturb it
reset_catalog(CAT)   # idempotent rerun
cat = catalog(CAT)
ns = namespace(cat, "lake")
print(f"Catalog: {type(cat).__name__}   namespaces: {cat.list_namespaces()}")

# %% [markdown]
# ## 1. Create a table *through the catalog*
#
# Note what you do **not** do: you never pick a path. The catalog owns the
# layout. That indirection is exactly what lets the catalog later vend
# credentials, enforce row filters, and plan scans on your behalf.
#
# `nullable=False` is not cosmetic — Iceberg tracks *required* vs *optional*
# per field, and a required field can never be silently dropped.

# %%
SCHEMA = pa.schema([
    pa.field("event_id",   pa.int64(),           nullable=False),
    pa.field("ts",         pa.timestamp("us"),   nullable=False),
    pa.field("model",      pa.string()),
    pa.field("latency_ms", pa.int64()),
    pa.field("cost_usd",   pa.float64()),
])

tbl = cat.create_table(f"{ns}.llm_events", schema=SCHEMA)
print(f"Created {tbl.name()}")
print(f"  location:  {tbl.location()}")
print(f"  metadata:  {tbl.metadata_location.rsplit('/', 1)[-1]}")
print(f"  format-v{tbl.format_version}")

# %% [markdown]
# ## 2. Hidden partitioning — the feature that killed Hive
#
# In Hive you partitioned by a **derived column** (`dt=2026-08-05`) that the
# user had to know about and filter on by hand. Forget it, and you full-scan
# the table. Every data team has that outage story.
#
# Iceberg stores the *transform* (`day(ts)`) in metadata instead. You filter on
# `ts` — the real column — and the engine derives the partition itself.

# %%
from pyiceberg.transforms import DayTransform  # noqa: E402

with tbl.update_spec() as spec:
    spec.add_field("ts", DayTransform(), "ts_day")

tbl = cat.load_table(f"{ns}.llm_events")  # refresh after a metadata change
print(f"Partition spec: {tbl.spec()}")
print("\nNote: 'ts_day' is NOT a column you insert. It is derived from ts.")

# %% [markdown]
# ## 3. Append 10 daily batches
#
# Each `append()` is one atomic commit → one snapshot. This is the same
# ACID guarantee Delta gives you, expressed through a different metadata tree.

# %%
MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]
COST_PER_CALL = {"claude-haiku-4-5": 0.0004, "claude-sonnet-4-6": 0.003, "claude-opus-4-7": 0.015}
ROWS_PER_DAY = 500
N_DAYS = 10


def day_batch(day: int) -> pa.Table:
    """One day of synthetic inference traffic."""
    models = [MODELS[i % 3] for i in range(ROWS_PER_DAY)]
    return pa.table({
        "event_id":   [day * ROWS_PER_DAY + i for i in range(ROWS_PER_DAY)],
        "ts":         [dtm.datetime(2026, 8, day, 3, i % 60) for i in range(ROWS_PER_DAY)],
        "model":      models,
        "latency_ms": [200 + (i * 7) % 3000 for i in range(ROWS_PER_DAY)],
        "cost_usd":   [COST_PER_CALL[m] for m in models],
    }, schema=SCHEMA)


for day in range(1, N_DAYS + 1):
    tbl.append(day_batch(day))

tbl = cat.load_table(f"{ns}.llm_events")
print(f"Rows:      {tbl.scan().to_arrow().num_rows:,}")
print(f"Snapshots: {len(tbl.snapshots())}   (one per commit)")
print(f"Data files: {tbl.inspect.files().num_rows}")

# %% [markdown]
# ## 4. Scan planning — count the files selected by the client
#
# `plan_files()` is the planning step itself: given a filter, which data files
# must actually be read? This lab plans the scan locally through PyIceberg;
# it does not demonstrate server-side planning.
#
# Watch: we filter on **`ts`**, never on `ts_day`.

# %%
scan_all = tbl.scan()
scan_one_day = tbl.scan(row_filter="ts >= '2026-08-05T00:00:00' and ts < '2026-08-06T00:00:00'")

files_all = len(list(scan_all.plan_files()))
files_one = len(list(scan_one_day.plan_files()))

print(f"Files to read, no filter:    {files_all}")
print(f"Files to read, one-day filter: {files_one}")
print(f"→ Pruning ratio: {files_all / max(files_one, 1):.0f}×   (target ≥ 5×)")
print(f"  rows returned: {scan_one_day.to_arrow().num_rows:,}")

PRUNE_RATIO = files_all / max(files_one, 1)
assert PRUNE_RATIO >= 5, f"expected ≥5x pruning, got {PRUNE_RATIO:.1f}x"

# %% [markdown]
# ### The Hive comparison, made concrete
#
# A Hive-style user who forgets the partition predicate reads **all** files.
# The Iceberg user cannot make that mistake — there is no partition column to
# forget. Same query intent, an order of magnitude difference in bytes scanned.

# %%
# Scale the toy numbers to a realistic file size and a metered engine
# (Athena/BigQuery bill per TB scanned; $5/TB is the long-standing list price).
FILE_MB, PRICE_PER_TB, QUERIES_PER_DAY = 512, 5.0, 10_000
waste_tb = (files_all - files_one) * FILE_MB / 1_048_576

print(f"Hive user who forgets `WHERE dt=...`:  reads {files_all} files")
print(f"Iceberg user filtering on `ts`:        reads {files_one} files")
print(f"\nAt {FILE_MB} MB/file and ${PRICE_PER_TB:.0f}/TB scanned:")
print(f"  wasted per query: {waste_tb * 1024:.1f} GB  =  ${waste_tb * PRICE_PER_TB:.3f}")
print(f"  × {QUERIES_PER_DAY:,} queries/day  =  ${waste_tb * PRICE_PER_TB * QUERIES_PER_DAY:,.0f}/day")
print("\nThat is the bill for one forgotten predicate. Hidden partitioning removes")
print("the opportunity to forget.")

# %% [markdown]
# ## 5. The three-tier metadata tree
#
# This is the structure the deck draws as a chain. Now walk it for real:
#
# ```
# catalog  →  metadata.json  →  manifest list  →  manifest files  →  data files
#             (schema, specs,   (one per         (file stats:
#              snapshot ptr)     snapshot)        min/max, counts)
# ```
#
# Every tier exists to let the tier above **skip** work below it.

# %%
snaps = tbl.inspect.snapshots()
mans = tbl.inspect.manifests()
files = tbl.inspect.files()

print(f"Tier 1  metadata.json     : {tbl.metadata_location.rsplit('/', 1)[-1]}")
print(f"Tier 2  manifest lists    : {snaps.num_rows} (one per snapshot)")
print(f"Tier 3  manifest files    : {mans.num_rows}")
print(f"        data files        : {files.num_rows}")
print(f"\nMetadata log entries: {tbl.inspect.metadata_log_entries().num_rows}")
print(f"Partitions tracked  : {tbl.inspect.partitions().num_rows}")

# %% [markdown]
# ### The cost of planning
#
# Metadata is not free. Count what a planner would have to open, and compare
# metadata bytes to data bytes — this ratio is *why* Iceberg v4 is redesigning
# the metadata tree, and why server-side planning matters at scale.

# %%
loc = tbl.location().replace("file://", "")
meta_bytes = du(f"{loc}/metadata")
data_bytes = du(f"{loc}/data")
print(f"data/     {human(data_bytes):>10}   ({count_files(f'{loc}/data')} parquet files)")
print(f"metadata/ {human(meta_bytes):>10}   ({count_files(f'{loc}/metadata', '.avro')} avro + "
      f"{count_files(f'{loc}/metadata', '.json')} json)")
print(f"→ metadata is {meta_bytes / max(data_bytes, 1) * 100:.1f}% of table size")
print("\nAt 10 rows/file this looks absurd. At 512 MB/file it is ~0.1%.")
print("Small files punish you TWICE: more data files AND more metadata to plan over.")

# %% [markdown]
# ## 6. Schema evolution by field-ID (not by name, not by position)
#
# Parquet columns are positional. Hive matched by name. Both break under
# rename/reorder. Iceberg assigns every field a **permanent integer ID**;
# names are just labels on top of it.
#
# So a rename is a *metadata-only* operation — zero files rewritten.

# %%
from pyiceberg.types import StringType  # noqa: E402

print("Field IDs before:", [(f.field_id, f.name) for f in tbl.schema().fields])

with tbl.update_schema() as upd:
    upd.add_column("tier", StringType(), doc="customer tier, added after 5000 rows existed")
tbl = cat.load_table(f"{ns}.llm_events")

with tbl.update_schema() as upd:
    upd.rename_column("latency_ms", "latency_millis")
tbl = cat.load_table(f"{ns}.llm_events")

print("Field IDs after :", [(f.field_id, f.name) for f in tbl.schema().fields])
print("\nlatency_ms → latency_millis kept field_id=4: a rename rewrote NO data.")
print("Old rows read back with tier=NULL — no backfill, no migration job.")

# %%
after = tbl.scan().to_arrow()
print(f"Rows still readable: {after.num_rows:,}")
print(f"Columns now: {after.column_names}")
print(f"tier nulls: {after.column('tier').null_count:,} (all pre-existing rows)")

# %% [markdown]
# ## 7. Time travel by snapshot
#
# Same idea as Delta's `versionAsOf`, different spelling. Every snapshot is
# addressable forever until you expire it (that's NB6).

# %%
snap_ids = [s.snapshot_id for s in tbl.snapshots()]
first, last = snap_ids[0], snap_ids[-1]

print(f"snapshot[0]  {first}: {tbl.scan(snapshot_id=first).to_arrow().num_rows:,} rows")
print(f"snapshot[-1] {last}: {tbl.scan(snapshot_id=last).to_arrow().num_rows:,} rows")
print(f"\nTotal snapshots retained: {len(snap_ids)}")

hist = tbl.inspect.history().to_pylist()
print("\nHistory (last 3):")
for h in hist[-3:]:
    print(f"  {h['made_current_at']}  snapshot={h['snapshot_id']}")

# %% [markdown]
# ## 8. Partition evolution — the thing Hive genuinely cannot do
#
# Traffic grew; daily partitions are now too coarse. In Hive this is a
# rewrite-the-whole-table migration. In Iceberg you change the spec and
# **old data stays where it is** — each data file remembers which spec wrote it.

# %%
from pyiceberg.transforms import IdentityTransform  # noqa: E402

with tbl.update_spec() as spec:
    spec.add_field("model", IdentityTransform(), "model_id")
tbl = cat.load_table(f"{ns}.llm_events")

tbl.append(day_batch(11).append_column("tier", pa.array(["gold"] * ROWS_PER_DAY))
           .rename_columns(["event_id", "ts", "model", "latency_millis", "cost_usd", "tier"]))
tbl = cat.load_table(f"{ns}.llm_events")

specs_in_use = set(tbl.inspect.files().column("spec_id").to_pylist())
print(f"Partition specs in use across data files: {sorted(specs_in_use)}")
print(f"Total rows readable across BOTH specs: {tbl.scan().to_arrow().num_rows:,}")
print("\nTwo layouts, one table, zero rewrites. This is the feature.")

# %% [markdown]
# ### 🔎 Bằng chứng bổ sung — mỗi data file nhớ spec đã ghi ra nó
#
# *(Cell do học viên thêm, chỉ đọc metadata.)*

# %%
from collections import Counter  # noqa: E402

print("Partition specs trong metadata:")
for s in tbl.metadata.partition_specs:
    print(f"  spec_id={s.spec_id}: {[(f.name, str(f.transform)) for f in s.fields]}")
print("Số data file theo spec_id:",
      dict(sorted(Counter(tbl.inspect.files().column("spec_id").to_pylist()).items())))
print("Field ID hiện tại:", [(f.field_id, f.name) for f in tbl.schema().fields])

# %% [markdown]
# ## 📝 Giải thích kết quả NB5 (Lò Văn Long — 2A202602541)
#
# **Số đo trên máy mình** (`pyiceberg` 0.12.0, SQLite catalog cục bộ):
#
# | Tiêu chí | Kết quả | Ngưỡng |
# |---|---|---|
# | Tạo bảng qua catalog | `cat.create_table("lake.llm_events")`. Mình không chọn path; catalog đặt bảng ở `warehouse/lake/llm_events`, format v2 | qua catalog |
# | Partition spec | `1000: ts_day: day(2)`, tức transform `day` trên field id 2 (`ts`) | `day(ts)` |
# | Hidden-partition pruning | `plan_files()`: không filter 10 file, filter 1 ngày trên **`ts`** 1 file → **10×**, trả 500 dòng | ≥ 5× |
# | Metadata tree | metadata.json (bản thứ 12, `00011-…`) → 10 manifest list → 10 manifest → 10 data file; metadata 136,0 KB / data 47,3 KB = **287,7%** (dao động ±0,1% giữa các lần chạy do tên file chứa UUID) | có báo tỷ lệ |
# | Rename | `(4, 'latency_ms')` → `(4, 'latency_millis')`, `tier` nhận id mới 6 | giữ field_id 4 |
# | Partition evolution | spec_id **[1, 2]** cùng tồn tại; đọc đủ **5.500** dòng (10 ngày × 500 + ngày 11) | ≥ 2 spec, đọc được |
#
# **Hidden partitioning hỗ trợ filter trên cột nguồn như thế nào?** Spec lưu **phép biến đổi** `day(ts)`
# trong metadata, không lưu một cột `ts_day` do người dùng tự ghi. Khi mình lọc
# `ts >= '2026-08-05' AND ts < '2026-08-06'`, PyIceberg *chiếu* điều kiện này qua transform thành điều kiện
# trên giá trị partition (`ts_day = 2026-08-05`), so với partition value lưu trong manifest, rồi loại 9/10
# file mà không mở chúng. Người dùng không cần biết `ts_day` tồn tại, nên không thể "quên" điều kiện
# partition. Với Hive, quên `WHERE dt=…` nghĩa là quét cả bảng. Theo phép tính của notebook (512 MB/file,
# $5/TB, 10.000 query/ngày), một điều kiện bị quên tốn khoảng **$220/ngày**.
#
# **Tỷ lệ metadata:data ~288% nói lên điều gì?** Mỗi `append` tạo 1 snapshot, nên sinh thêm 1 metadata.json,
# 1 manifest list và 1 manifest. Metadata tăng theo **số commit và số file**, không theo lượng dữ liệu. Ở đây
# mỗi file chỉ 500 dòng (~4,7 KB) nên metadata lớn gấp gần 3 lần dữ liệu. Với file 512 MB, tỷ lệ này chỉ
# còn khoảng 0,1%. File nhỏ và commit dày gây hại hai lần: nhiều file phải đọc và nhiều metadata phải
# plan qua (liên hệ NB6).
#
# **Field ID giúp gì khi rename?** Iceberg gán mỗi cột một **ID số nguyên cố định**; tên chỉ là nhãn. File
# Parquet cũ lưu field_id trong schema của chúng, và reader ghép cột theo ID chứ không theo tên hay vị trí.
# Rename `latency_ms → latency_millis` vì thế chỉ là một commit metadata: 0 file dữ liệu bị ghi lại, dữ liệu
# cũ vẫn đọc ra dưới tên mới. Cột `tier` thêm sau nhận ID mới (6); 5.000 dòng cũ đọc ra `tier = null` mà
# không cần backfill. Nếu ghép theo tên như Hive, rename sẽ làm cột cũ "biến mất". Nếu ghép theo vị trí như
# Parquet thuần, thêm hoặc đổi thứ tự cột sẽ đọc nhầm dữ liệu.
#
# **Vì sao partition evolution không bắt buộc file cũ đổi layout ngay?** Mỗi data file trong manifest ghi lại
# `spec_id` đã dùng khi ghi nó. Cell bằng chứng cho thấy 10 file cũ thuộc spec 1 `day(ts)`; batch ngày 11
# ghi ra 3 file thuộc spec 2 `day(ts)` + `identity(model)` (mỗi model một file); spec 0 là spec rỗng lúc tạo
# bảng và không có file nào. Khi plan, Iceberg đánh giá filter theo **spec riêng của từng file**, nên
# hai layout cùng tồn tại trong một bảng mà vẫn đúng. Không cần dừng hệ thống để ghi lại cả bảng như Hive.
# Dữ liệu cũ có thể được ghi lại sang layout mới dần dần khi chạy compaction (NB6), hoặc giữ nguyên nếu
# hiếm khi được truy vấn.
#
# **Giới hạn của lab:** catalog là SQLite cục bộ và việc plan diễn ra ở phía client. Lab không minh họa
# remote planning, credential vending hay phân quyền của REST catalog ở production.

# %% [markdown]
# ## ✅ NB5 pass criteria
#
# | Check | Target |
# |---|---|
# | Hidden-partition pruning ratio | ≥ 5× (printed in §4) |
# | Snapshots retained | ≥ 10 |
# | Schema evolved, field IDs stable | `latency_millis` keeps `field_id=4` |
# | Partition evolution | ≥ 2 distinct `spec_id`s, table still fully readable |

# %%
checks = {
    "pruning ratio ≥ 5x":        PRUNE_RATIO >= 5,
    "≥ 10 snapshots":            len(tbl.snapshots()) >= 10,
    "field_id stable on rename": [f.field_id for f in tbl.schema().fields if f.name == "latency_millis"] == [4],
    "≥ 2 partition specs":       len(specs_in_use) >= 2,
    "all rows readable":         tbl.scan().to_arrow().num_rows == (N_DAYS + 1) * ROWS_PER_DAY,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB5 incomplete — see FAIL rows above"
print("\nNB5 complete.")
