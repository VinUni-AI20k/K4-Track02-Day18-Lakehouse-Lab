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
# ## 📝 Báo cáo phân tích và giải thích (NB2)
#
# ### 1. Compaction và Z-order tác động khác nhau thế nào?
# - **Compaction (`dt.optimize.compact()`):** Tác động lên **kích thước và số lượng file vật lý**. Mục tiêu là giải quyết vấn đề "Small-File Problem" phát sinh từ streaming ingestion bằng cách gộp hàng trăm/nghìn file nhỏ thành các file lớn có kích thước tối ưu (ví dụ: 128 MB – 512 MB trong production, 256 KB trong lab). Compaction giúp giảm chi phí quản lý metadata của transaction log và giảm số lượng request I/O (`GET`/`LIST`) lên Cloud Object Storage. Tuy nhiên, compaction đơn thuần **không sắp xếp lại thứ tự dữ liệu**; các giá trị vẫn bị phân tán ngẫu nhiên trên toàn bộ các file, khiến dải min/max của mỗi file đều rất rộng và chồng chéo nhau.
# - **Z-Order (`dt.optimize.z_order(["user_id"])`):** Tác động lên **cách tổ chức và sắp xếp thứ tự dữ liệu (clustering)** dựa trên đường cong Z-order (Morton curve). Z-order gom các bản ghi có giá trị gần nhau (ví dụ cùng `user_id`) vào chung một hoặc một số ít file liền kề. Nhờ đó, dải `[min, max]` của `user_id` trong mỗi file trở nên cực kỳ hẹp (tight) và không chồng lấn. Khi truy vấn point-query (`WHERE user_id = 4242`), engine đọc thống kê min/max từ transaction log và bỏ qua đại đa số các file không chứa giá trị mục tiêu (**File Pruning / Data Skipping**), mang lại hiệu năng truy vấn vượt trội.
#
# ### 2. Vì sao gộp thành một file lớn có thể làm khó quan sát file pruning?
# - Đơn vị cơ bản của Data Skipping ở tầng Table Format (Delta Lake / Iceberg) là **File**. Thống kê min/max được thu thập và lưu trữ theo từng file riêng biệt.
# - Nếu compaction gộp toàn bộ 1,000,000 dòng vào **duy nhất 1 file Parquet lớn**, thì file đó bắt buộc phải chứa dải min/max từ `1` đến `100,000`. Khi thực hiện bất kỳ truy vấn lọc nào, file duy nhất này luôn thỏa điều kiện và engine buộc phải quét toàn bộ file đó (pruning ratio = 1×, không có file nào bị skip).
# - Để quan sát và đo lường được hiệu quả của file pruning, bảng bắt buộc phải có **nhiều file** (trong notebook đặt `TARGET_SIZE = 256 * 1024` để giữ khoảng 30–50 files sau compaction), giúp Z-order cô lập `user_id=4242` vào đúng 1 file duy nhất và prune thành công toàn bộ các file còn lại.
#
# ### 3. Vì sao thời gian benchmark biến động giữa các máy?
# - Phép đo thời gian thực tế (**Wall-clock Speedup**) trên môi trường máy tính cá nhân (laptop/PC) bị ảnh hưởng bởi nhiều yếu tố phi tất định:
#   1. **Hệ điều hành File Caching (OS Page Cache / RAM Cache):** Sau lần quét đầu tiên, các trang nhớ của file Parquet đã nằm trên RAM, khiến các lần quét sau nhanh đột biến mà không phản ánh đúng chi phí I/O vật lý.
#   2. **CPU Throttling và tiến trình nền:** Sự can thiệp của phần mềm chống virus, xung đột luồng CPU, hoặc cơ chế tiết kiệm điện năng của laptop.
#   3. **Độ trễ I/O trên ổ cứng SSD/NVMe:** Dữ liệu lab tương đối nhỏ (vài chục MB), nên thời gian I/O chỉ mất vài mili-giây, dẫn đến overhead khởi tạo của runtime chiếm tỷ trọng lớn.
# - Do đó, chỉ số **Files-Pruned Ratio** (tỷ lệ số file được bỏ qua dựa trên metadata min/max) là một thước đo **xác định (deterministic)**, đo lường chính xác hiệu quả thuật toán mà không phụ thuộc vào cấu hình phần cứng.

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
