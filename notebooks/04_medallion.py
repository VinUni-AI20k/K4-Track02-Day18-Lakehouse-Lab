# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # NB4 — Medallion Pipeline (Bronze → Silver → Gold), lightweight
#
# **Use case:** LLM observability — exact schema from slide §8 (Lakehouse cho AI/ML) medallion frame.
# Maps to deliverable bullet 4 (the Milestone-1 Lakehouse artifact).
#
# Pre-req: ran `make data` — but if you jumped straight here, the cell below
# generates the Bronze sample for you rather than failing on a missing path.

# %%
import _setup  # noqa: F401  -- adds scripts/ to sys.path
from pathlib import Path

import polars as pl
import duckdb
from deltalake import DeltaTable, write_deltalake
from lakehouse import path, reset

BRONZE = path("bronze", "llm_calls_raw")
SILVER = path("silver", "llm_calls")
GOLD   = path("gold",   "llm_daily_metrics")

# Self-healing pre-req (same pattern as NB7/NB8). Without this, skipping
# `make data` surfaces as a raw `Os { code: 2, kind: NotFound }` from the Rust
# layer — technically correct, useless to a student.
if not Path(BRONZE).exists():
    print("Bronze not found — running scripts/generate_data_lite.py first ...")
    import generate_data_lite

    generate_data_lite.main()

# %% [markdown]
# ## Bronze — verify raw is loaded

# %%
bronze_n = DeltaTable(BRONZE).to_pyarrow_table().num_rows
print(f"Bronze rows: {bronze_n:,}")
print(pl.from_arrow(DeltaTable(BRONZE).to_pyarrow_table().slice(0, 2)))

# %% [markdown]
# ## Silver — parse, validate, dedup
#
# Rules: drop malformed JSON, dedupe by `request_id`, project typed columns.

# %%
reset(SILVER)

# DuckDB does the JSON parse + dedup in one query — Polars also works,
# DuckDB just has nicer JSON syntax for this case.
# DuckDB reads Delta through Arrow, not through `delta_scan()`. The latter
# autoloads an extension over the network; Arrow registration is offline and
# zero-copy, so the lab works on a locked-down machine.
con = duckdb.connect()
con.register("bronze", DeltaTable(BRONZE).to_pyarrow_table())

silver_arrow = con.sql(f"""
    WITH parsed AS (
      SELECT
        request_id,
        ts,
        CAST(ts AS DATE)                            AS date,
        json_extract_string(raw_json, '$.model')          AS model,
        json_extract_string(raw_json, '$.user_id')        AS user_id,
        CAST(json_extract(raw_json, '$.usage.input')  AS INTEGER) AS prompt_tokens,
        CAST(json_extract(raw_json, '$.usage.output') AS INTEGER) AS completion_tokens,
        CAST(json_extract(raw_json, '$.latency_ms')   AS INTEGER) AS latency_ms,
        json_extract_string(raw_json, '$.status')         AS status,
        ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY ts) AS rn
      FROM bronze
    )
    SELECT request_id, ts, date, model, user_id,
           prompt_tokens, completion_tokens, latency_ms, status
    FROM parsed
    WHERE rn = 1 AND model IS NOT NULL
""").arrow()

write_deltalake(SILVER, silver_arrow, mode="overwrite", partition_by=["date"])

silver_n = DeltaTable(SILVER).to_pyarrow_table().num_rows
print(f"Silver rows: {silver_n:,}  (Bronze {bronze_n:,} → dedup dropped {bronze_n - silver_n:,})")
assert silver_n < bronze_n, (
    "Silver has the same row count as Bronze — dedup did not run. "
    "Did you regenerate Bronze with the latest generator (which injects retries)?"
)

# %% [markdown]
# ## Gold — aggregate to (date, model) metrics

# %%
reset(GOLD)

# Illustrative cost model — NOT canonical pricing.
# (input USD / 1M tokens, output USD / 1M tokens)
COST_TABLE = """
  VALUES
    ('claude-haiku-4-5',  0.80,  4.00),
    ('claude-sonnet-4-6', 3.00, 15.00),
    ('claude-opus-4-7', 15.00, 75.00)
"""

con.register("silver", DeltaTable(SILVER).to_pyarrow_table())
gold_arrow = con.sql(f"""
    WITH cost(model, c_in, c_out) AS ({COST_TABLE})
    SELECT
      s.date,
      s.model,
      QUANTILE_CONT(s.latency_ms, 0.50) AS p50_latency_ms,
      QUANTILE_CONT(s.latency_ms, 0.95) AS p95_latency_ms,
      SUM(s.prompt_tokens)              AS total_prompt_tokens,
      SUM(s.completion_tokens)          AS total_completion_tokens,
      AVG(CASE WHEN s.status <> 'ok' THEN 1.0 ELSE 0.0 END) AS error_rate,
      (SUM(s.prompt_tokens)     * c.c_in  / 1e6) +
      (SUM(s.completion_tokens) * c.c_out / 1e6) AS cost_usd
    FROM silver s
    JOIN cost c USING (model)
    GROUP BY s.date, s.model, c.c_in, c.c_out
    ORDER BY s.date, s.model
""").arrow()

write_deltalake(GOLD, gold_arrow, mode="overwrite", partition_by=["date"])

# Z-order for fast filter-by-model dashboards
DeltaTable(GOLD).optimize.z_order(["model"])

# %% [markdown]
# ## Verify Gold

# %%
gold_df = pl.from_arrow(DeltaTable(GOLD).to_pyarrow_table())
print(gold_df)

# Slide-5 deliverable: "Gold p50/p95/cost qua ≥ 7 ngày". Make that explicit.
n_dates = gold_df.select("date").n_unique()
n_models = gold_df.select("model").n_unique()
print(
    f"\n──── Gold deliverable metrics ────\n"
    f"  Distinct dates:   {n_dates:>3}   (target ≥ 7)\n"
    f"  Distinct models:  {n_models:>3}\n"
    f"  Total Gold rows:  {gold_df.height:>3}   (= dates × models)"
)
assert n_dates >= 7, (
    f"Gold has only {n_dates} dates — slide deliverable requires ≥ 7. "
    "Re-run `make data` (the generator spreads across 7 UTC days)."
)

# %% [markdown]
# ### 🔎 Bằng chứng bổ sung — kiểm tra đủ điều kiện Gold mà notebook chưa assert
#
# *(Cell do học viên thêm, chỉ đọc.)* In **toàn bộ** Gold và tự kiểm từng điều kiện của rubric:
# ≥ 7 ngày × 3 model, p50 ≤ p95, `cost_usd` > 0, `error_rate` ∈ [0, 1].

# %%
with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=140, fmt_str_lengths=20):
    print(gold_df.sort(["date", "model"]).select(
        "date", "model", "p50_latency_ms", "p95_latency_ms", "error_rate",
        pl.col("cost_usd").round(2)))

models_per_date = gold_df.group_by("date").agg(pl.col("model").n_unique().alias("n"))
gold_checks = {
    "≥ 7 dates":                       n_dates >= 7,
    "3 models on every date":          models_per_date["n"].min() == 3,
    "p50 ≤ p95 on every row":          bool((gold_df["p50_latency_ms"] <= gold_df["p95_latency_ms"]).all()),
    "cost_usd > 0 on every row":       bool((gold_df["cost_usd"] > 0).all()),
    "0 ≤ error_rate ≤ 1 on every row": bool(gold_df["error_rate"].is_between(0, 1).all()),
}
for k, v in gold_checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(gold_checks.values()), "Gold chưa đạt đủ điều kiện"

# %% [markdown]
# ### 🔎 Vì sao Gold có 8 ngày chứ không phải 7? — múi giờ của phiên DuckDB
#
# Generator rải `ts` (kiểu timestamp **có múi giờ UTC**) trên đúng 7 ngày UTC. Nhưng
# `CAST(ts AS DATE)` trong DuckDB dùng `TimeZone` của phiên, mặc định là múi giờ máy.

# %%
print("DuckDB TimeZone:", con.sql("SELECT current_setting('TimeZone')").fetchone()[0])
print("ts min/max (theo TimeZone phiên):",
      con.sql("SELECT CAST(min(ts) AS VARCHAR), CAST(max(ts) AS VARCHAR) FROM silver").fetchone())
print("\nSố request Silver theo `date` (múi giờ phiên):")
for d, n in con.sql("SELECT CAST(date AS VARCHAR), count(*) FROM silver GROUP BY 1 ORDER BY 1").fetchall():
    print(f"  {d}  {n:>6,}")
utc_days = con.sql("SELECT count(DISTINCT CAST(timezone('UTC', ts) AS DATE)) FROM silver").fetchone()[0]
print(f"\nSố ngày nếu cắt theo UTC: {utc_days}")

print("\nPhân bố status trong Silver (đầu vào của error_rate):")
for s, n, pct in con.sql("""SELECT status, count(*), round(100.0 * count(*) / sum(count(*)) OVER (), 2)
                            FROM silver GROUP BY 1 ORDER BY 2 DESC""").fetchall():
    print(f"  {s:<13} {n:>7,}  {pct:>5}%")

from lakehouse import ROOT  # noqa: E402

print("\nVị trí 3 bảng trên storage (tính từ gốc repo):")
for name, p_ in [("Bronze", BRONZE), ("Silver", SILVER), ("Gold", GOLD)]:
    n_parts = len(list(Path(p_).glob("date=*")))
    n_commits = len(list(Path(p_).glob("_delta_log/*.json")))
    layout = f"{n_parts} partition date=…" if n_parts else "không partition"
    print(f"  {name:<6} {Path(p_).relative_to(ROOT.parent).as_posix():<32} {layout:<20} {n_commits} commit")

# %% [markdown]
# ## 📝 Giải thích kết quả NB4 (Lò Văn Long — 2A202602541)
#
# **Số đo trên máy mình:**
#
# | Tầng | Vị trí | Số dòng |
# |---|---|---|
# | Bronze | `_lakehouse/bronze/llm_calls_raw` (JSON thô) | 200.000 |
# | Silver | `_lakehouse/silver/llm_calls` (partition theo `date`) | **190.052** (dedup bỏ 9.948 dòng) |
# | Gold | `_lakehouse/gold/llm_daily_metrics` (partition `date`, Z-order theo `model`) | 24 = **8 ngày × 3 model** |
#
# Kiểm tra Gold (cell bằng chứng, assert thật): ≥ 7 ngày ✔, đủ 3 model mỗi ngày ✔, p50 ≤ p95 ở mọi dòng ✔
# (ví dụ Haiku khoảng 560 / 1.130 ms, Sonnet ~1.380 / 2.750 ms, Opus ~3.000 / 6.000 ms), `cost_usd` > 0 ✔,
# `error_rate` ∈ [0, 1] ✔ (khoảng 0,04–0,06). Số dòng bị bỏ (9.948) **khớp đúng** số request_id trùng mà
# generator chèn vào (`unique request_ids: 190,052`).
#
# **Vì sao Gold có 8 ngày, không phải 7?** Generator rải `ts` trên đúng 7 ngày **UTC** (01/04 00:00 → 07/04
# 23:59 UTC). Nhưng `CAST(ts AS DATE)` trong DuckDB dùng `TimeZone` của phiên, ở máy mình là `Asia/Bangkok`
# (UTC+7). Ranh giới ngày vì thế lệch 7 giờ: ngày 01/04 chỉ có 17 giờ dữ liệu (19.271 request), ngày 08/04
# chỉ có 7 giờ (7.915 request); cắt theo UTC thì đúng 7 ngày. Rubric (≥ 7 ngày × 3 model) vẫn đạt. Tuy
# nhiên đây là một bẫy thật: **cùng pipeline mà chạy ở máy khác múi giờ sẽ cho Gold khác nhau**, và
# `cost_usd` của 01/04, 08/04 thấp chỉ vì đó là ngày thiếu giờ. Mình giữ nguyên code lab để không đổi đề.
# Ở production nên cố định `SET TimeZone='UTC'`, hoặc tính `date` theo một múi giờ nghiệp vụ đã thống nhất
# ngay từ lúc ingest.
#
# **Dedup ở Silver giải quyết vấn đề gì?** Client retry gửi lại cùng `request_id` (khoảng 5% ở đây). Không
# dedup thì số request, token và chi phí bị đếm trùng khoảng 5%; p50/p95 và error rate cũng bị lệch vì một
# request được tính nhiều lần. Silver dùng `ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY ts)` và giữ
# bản ghi **sớm nhất**. Đồng thời bỏ JSON lỗi (`model IS NULL`) và ép kiểu thành các cột có kiểu rõ ràng.
#
# **Vì sao dashboard đọc Gold?** Gold chỉ có 24 dòng đã tổng hợp sẵn, so với 190.052 dòng Silver. Định nghĩa
# chỉ số (p50/p95, công thức cost, error rate) được tính **một lần, thống nhất** thay vì mỗi dashboard tự
# viết lại. Truy vấn nhanh và rẻ (partition theo `date`, Z-order theo `model` cho filter theo model). Bronze
# và Silver chứa dữ liệu chi tiết (user_id) mà người xem dashboard không cần đọc.
#
# **Cách tính error rate và cost có phù hợp với dữ liệu không?** Chỉ phù hợp một phần:
# - `error_rate = AVG(status <> 'ok')` gộp **`rate_limited` (2,99%)** với **`error` (1,98%)**. Rate limit
#   thường do quota phía client, không phải lỗi model. Nên tách thành 2 cột để cảnh báo đúng đội.
# - `cost_usd` cộng token của **mọi** request, kể cả request bị rate-limit hay lỗi. Thực tế request 429
#   thường không bị tính tiền, nên chi phí có thể bị **ước cao** khoảng 3–5%. Ngược lại, dedup chỉ giữ lần
#   gọi đầu, trong khi các lần retry đã thật sự chạy cũng có thể bị tính tiền. Cần thống nhất định nghĩa
#   "chi phí" với bên tài chính.
# - Bảng giá là **giá minh họa của lab**, không phải giá thật. `QUANTILE_CONT` nội suy giữa các giá trị nên
#   p50/p95 có thể là số lẻ (ví dụ 2995.5).

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] All three tables exist under `_lakehouse/{bronze,silver,gold}/`
# - [ ] Silver has fewer rows than Bronze (dedup worked)
# - [ ] Gold spans ≥ 7 dates × 3 models (slide §8 medallion contract)
# - [ ] Cost & error_rate columns populated and non-zero
