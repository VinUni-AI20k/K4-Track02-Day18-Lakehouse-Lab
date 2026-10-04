# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # NB2 — Small-File Problem & OPTIMIZE + Z-order (lightweight)
#
# Maps to slide §6 Storage Optimization (& Anti-Patterns) + deliverable bullet 2.
#
# > Spark equivalent: `OPTIMIZE delta.\`path\` ZORDER BY (user_id)`
# > delta-rs:        `dt.optimize.compact()` + `dt.optimize.z_order(["user_id"])`
#
# **Key idea:** Z-order's value is *file-skipping*. With min/max stats per
# file, Delta prunes files whose range can't contain your predicate. That
# only works when the table has *multiple files* — if `compact()` collapses
# everything to one file, Z-order has nothing to prune.

# %%
import _setup  # noqa: F401  -- adds scripts/ to sys.path
import time, random
import polars as pl
import duckdb
from deltalake import DeltaTable, write_deltalake
from lakehouse import path, reset

table_path = path("scratch", "events_smallfiles")
reset(table_path)  # idempotent

# %% [markdown]
# ## 1. Manufacture the small-file problem
#
# 200 tiny appends → 200 small files. Realistic streaming-ingestion shape.
# Each batch is 5K rows × wider schema (≈200 B/row payload) so post-compaction
# we still have multiple files with a 256 KB target — required for Z-order
# skipping to actually skip something in the benchmark.

# %%
random.seed(42)
TARGET_USER = 4242  # the point-query needle

# Pre-built payload pool keeps row generation fast while making each row fat
# enough that compaction doesn't collapse 1M rows into a single 8 MB file.
PAYLOADS = [("p" * 200) + str(i) for i in range(64)]

for batch in range(200):
    rows = pl.DataFrame({
        "event_id":  list(range(batch * 5_000, (batch + 1) * 5_000)),
        "kind":      [random.choice(["click", "view", "scroll", "purchase"]) for _ in range(5_000)],
        # 100K distinct users → before z-order, the target user is scattered
        # across many files; after z-order it clusters into ~1 file.
        "user_id":   [random.randint(1, 100_000) for _ in range(5_000)],
        "payload":   [random.choice(PAYLOADS) for _ in range(5_000)],
    })
    mode = "overwrite" if batch == 0 else "append"
    write_deltalake(table_path, rows.to_arrow(), mode=mode)

dt = DeltaTable(table_path)
files_before = len(dt.file_uris())
print(f"Files before OPTIMIZE: {files_before}")

# %% [markdown]
# ## 2. Benchmark BEFORE optimize
#
# We use delta-rs's native filter pushdown (`to_pyarrow_table(filters=...)`)
# which reads per-file `min`/`max` stats from the transaction log and skips
# files whose range can't contain the predicate. That's the mechanism we
# want to measure — the same one Spark/Trino use.

# %%
def bench(label: str, runs: int = 3) -> float:
    """Median of `runs` point-queries using Delta's stats-based file pruning."""
    times = []
    n = 0
    for _ in range(runs):
        dt_local = DeltaTable(table_path)  # fresh metadata read
        t0 = time.perf_counter()
        tbl = dt_local.to_pyarrow_table(
            filters=[("user_id", "=", TARGET_USER), ("kind", "=", "purchase")]
        )
        n = tbl.num_rows
        times.append(time.perf_counter() - t0)
    times.sort()
    median = times[len(times) // 2]
    print(f"{label:25s}  count={n}  median={median*1000:6.1f} ms  (n={runs})")
    return median

before = bench("BEFORE OPTIMIZE")

# %% [markdown]
# ## 3. OPTIMIZE (compact small files) + Z-ORDER (co-locate by user_id)
#
# `target_size` is 256 KB so we keep multiple files post-compact — enough
# for Z-order's file-skipping to actually skip something.

# %%
TARGET_SIZE = 256 * 1024  # 256 KB — keeps ~50 files post-compact for visible pruning

dt = DeltaTable(table_path)
dt.optimize.compact(target_size=TARGET_SIZE)
dt.optimize.z_order(["user_id"], target_size=TARGET_SIZE)

dt = DeltaTable(table_path)  # refresh
files_after = len(dt.file_uris())
print(f"Files after OPTIMIZE+ZORDER: {files_after}  (was {files_before})")

# %% [markdown]
# ## 4. Benchmark AFTER

# %%
after = bench("AFTER OPTIMIZE+ZORDER")
print(f"\nSpeedup: {before/max(after, 1e-6):.1f}×  (target ≥ 3×)")
print(f"File reduction: {files_before} → {files_after}  ({files_before/max(files_after,1):.0f}× fewer)")

# %% [markdown]
# ## 5. Why this works — inspect file-level stats
#
# Delta stores per-file `min`/`max` for stat-eligible columns in the
# transaction log. After Z-order, `user_id` ranges per file are tight and
# non-overlapping; the engine prunes files whose range excludes 4242.

# %%
import json
import os

log_dir = os.path.join(table_path, "_delta_log")
last_log = sorted(f for f in os.listdir(log_dir) if f.endswith(".json"))[-1]
print(f"Inspecting {last_log}:")
hits = 0
ranges = []
with open(os.path.join(log_dir, last_log)) as fh:
    for line in fh:
        e = json.loads(line)
        if "add" in e and "stats" in e["add"]:
            stats = json.loads(e["add"]["stats"])
            mn = stats.get("minValues", {}).get("user_id")
            mx = stats.get("maxValues", {}).get("user_id")
            if mn is not None:
                ranges.append((mn, mx))
                if mn <= TARGET_USER <= mx:
                    hits += 1
for mn, mx in sorted(ranges):
    marker = " ← contains target" if mn <= TARGET_USER <= mx else ""
    print(f"  file user_id range: [{mn:>6}, {mx:>6}]{marker}")

# Slide-5 deliverable allows EITHER metric — print both so the student can
# pick whichever the grader screenshots:
#   Speedup ≥ 3×              (wall-clock, noisy on local SSD)
#   Files-pruned ratio ≥ 10×  (deterministic, the truer Z-order metric)
pruned_ratio = files_after / max(hits, 1)
print(
    f"\n──── Z-order deliverable metrics ────\n"
    f"  Speedup (wall-clock):   {before/max(after, 1e-6):>5.1f}×   (target ≥ 3×)\n"
    f"  Files-pruned ratio:     {pruned_ratio:>5.1f}×   (target ≥ 10×)   "
    f"[{hits} of {files_after} files cover user_id={TARGET_USER}]"
)

# %% [markdown]
# ### 🔎 Bằng chứng bổ sung — compaction một mình có giúp pruning không?
#
# *(Cell do học viên thêm, chỉ đọc log.)* Dùng time travel trên metadata: version 199 là trước
# OPTIMIZE (200 append = v0…v199), v200 là sau `compact()`, v201 là sau `z_order()`. Đếm số file
# có khoảng [min, max] của `user_id` chứa user 4242, tức là file engine **không** thể bỏ qua.

# %%
import pyarrow as pa


def files_covering(version: int) -> tuple[int, int]:
    aa = pa.table(DeltaTable(table_path, version=version).get_add_actions(flatten=True)).to_pylist()
    return sum(1 for f in aa if f["min.user_id"] <= TARGET_USER <= f["max.user_id"]), len(aa)


for v, label in [(199, "trước OPTIMIZE"), (200, "sau compact()"), (201, "sau z_order()")]:
    must_read, total = files_covering(v)
    print(f"  v{v} {label:<16} phải đọc {must_read:>3}/{total:<3} file  "
          f"→ pruning {total / max(must_read, 1):5.1f}×")

# %% [markdown]
# ## 📝 Giải thích kết quả NB2 (Lò Văn Long — 2A202602541)
#
# **Số đo trên máy mình:**
#
# | Chỉ số | Trước | Sau | Ngưỡng |
# |---|---|---|---|
# | Số file | 200 (200 append × 5K dòng) | 55 (compact + Z-order, target 256 KB) | ≥ 100 trước; giảm rõ |
# | Point query `user_id=4242 AND kind='purchase'` | 182,7 ms | 17,1 ms | — |
# | Speedup (wall-clock, median 3 lần) | | **10,7×** (lần chạy nộp bài; các lần chạy thử trên máy mình dao động 10,7×–11,2×) | ≥ 3× |
# | Files-pruned ratio | | **55×** (1/55 file chứa user 4242) | ≥ 10× |
#
# Đạt **cả hai** ngưỡng, dù rubric chỉ cần một. Kết quả truy vấn trước và sau giống nhau (`count=5`),
# nên tối ưu không làm thay đổi dữ liệu.
#
# **Compaction và Z-order tác động khác nhau thế nào?** Cell bằng chứng (time travel trên log) trả lời trực tiếp:
# - **v199 (trước OPTIMIZE):** 200/200 file đều có khoảng `user_id` gần trọn [1, 100000], vì mỗi batch
#   random user. Stats không loại được file nào, phải mở cả 200 file nhỏ.
# - **v200 (chỉ `compact()`):** còn 67 file nhưng **vẫn phải đọc 67/67**. Compaction chỉ gộp file nhỏ thành
#   file to hơn: giảm overhead mở file, đọc footer và số entry trong log. Nó không sắp xếp dữ liệu, nên mỗi
#   file vẫn trộn đủ mọi user và pruning = 1×.
# - **v201 (sau `z_order(["user_id"])`):** dữ liệu được sắp lại theo `user_id` (với 1 cột, Z-order tương
#   đương sort). Mỗi file chỉ phủ khoảng ~1.850 user liền nhau và không chồng lấn (xem bảng range ở trên),
#   nên engine đọc min/max trong log và bỏ qua 54/55 file.
#
# Tóm lại, compaction giải quyết **số lượng** file, còn Z-order/clustering làm cho **stats có ích** để skip file.
#
# **Vì sao gộp thành một file lớn làm khó quan sát pruning?** File pruning hoạt động ở đơn vị *file*. Nếu
# OPTIMIZE gộp hết vào 1 file thì file đó có min = 1, max = 100000 và luôn "có thể chứa" mọi user: tỷ lệ
# pruning = 1/1 = 1×, dù dữ liệu bên trong đã sort. Vì thế lab đặt `target_size = 256 KB` để còn khoảng 55
# file. Ở production, target 128–512 MB trên bảng hàng trăm GB vẫn cho ra hàng nghìn file, nên pruning vẫn
# có tác dụng. Khi đó việc skip ở mức row group bên trong file cũng giúp thêm.
#
# **Vì sao thời gian benchmark biến động giữa các máy?** Wall-clock phụ thuộc vào page cache của hệ điều hành
# (lần đọc sau có thể không chạm đĩa), loại ổ (SSD/HDD), CPU và số core, tiến trình nền, và **Windows Defender
# quét file mới tạo** (200 file nhỏ vừa ghi). Mỗi phía chỉ đo median của 3 lần. Ngay trên máy mình, hai lần
# chạy liên tiếp đã cho 10.7× và 11.2×. Ngược lại, files-pruned ratio được tính từ metadata nên luôn ra 55×
# trên mọi máy. Đó là lý do rubric chấp nhận nó làm ngưỡng thay thế.

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] Speedup ≥ 3× **or** files-pruned ratio ≥ 10× (slide §6 allows either)
# - [ ] File count dropped substantially after compact()
# - [ ] Stats inspection shows ~1 file covers `user_id=4242`
# - [ ] Screenshot the printed numbers

# %%
speedup = before / max(after, 1e-6)
checks = {
    "compaction reduced file count":  files_after < files_before,
    "speedup ≥ 3x OR pruning ≥ 10x":  speedup >= 3 or pruned_ratio >= 10,
    "stats isolate the target user":  hits <= max(2, files_after // 4),
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print(f"\n  (speedup={speedup:.1f}x, pruning={pruned_ratio:.1f}x — the slide accepts EITHER;")
print("   wall-clock is noisy on a laptop, which is why file-pruning is the fallback.)")
assert all(checks.values()), "NB2 incomplete — see FAIL rows above"
print("\nNB2 complete.")
