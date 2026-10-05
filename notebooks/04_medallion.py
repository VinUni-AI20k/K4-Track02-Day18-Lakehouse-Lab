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
# `ts` is TIMESTAMPTZ in UTC. DuckDB's CAST(ts AS DATE) uses the session time
# zone, which defaults to the machine's local zone — on a UTC+7 laptop that
# shifts every day boundary by 7 hours (8 partial "days" instead of 7 UTC
# days). Pin the session to UTC so `date` means the UTC calendar day.
con.sql("SET TimeZone = 'UTC'")
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
gold_df = pl.from_arrow(DeltaTable(GOLD).to_pyarrow_table()).sort(["date", "model"])
with pl.Config(tbl_rows=30, tbl_width_chars=160, fmt_str_lengths=20):
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
# ## ✅ Deliverable check
# - [ ] All three tables exist under `_lakehouse/{bronze,silver,gold}/`
# - [ ] Silver has fewer rows than Bronze (dedup worked)
# - [ ] Gold spans ≥ 7 dates × 3 models (slide §8 medallion contract)
# - [ ] Cost & error_rate columns populated and non-zero

# %% [markdown]
# ## Gold quality checks
#
# The original notebook asserts only the date count. These checks make the rest
# of the Gold contract explicit: every (date, model) cell present, p50 ≤ p95,
# positive cost, error_rate within [0, 1], and all three layers on disk.

# %%
silver_dates = pl.from_arrow(DeltaTable(SILVER).to_pyarrow_table()).group_by("date").len().sort("date")
print("Silver rows per UTC date:")
for d, n in silver_dates.iter_rows():
    print(f"  {d}  {n:>7,}")

per_date_models = gold_df.group_by("date").agg(pl.col("model").n_unique().alias("models"))
layers = {name: (Path(p) / "_delta_log").exists() for name, p in
          [("bronze", BRONZE), ("silver", SILVER), ("gold", GOLD)]}
checks = {
    "bronze/silver/gold all on disk":      all(layers.values()),
    "silver < bronze (dedup)":             silver_n < bronze_n,
    "gold >= 7 dates":                     n_dates >= 7,
    "3 models":                            n_models == 3,
    "every date has all 3 models":         per_date_models["models"].min() == 3,
    "p50 <= p95 everywhere":               (gold_df["p50_latency_ms"] <= gold_df["p95_latency_ms"]).all(),
    "cost_usd > 0 everywhere":             (gold_df["cost_usd"] > 0).all(),
    "error_rate in [0, 1]":                gold_df["error_rate"].is_between(0, 1).all(),
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")

print()
print("Weekly cost by model (illustrative prices):")
print(gold_df.group_by("model").agg(
    pl.col("cost_usd").sum().round(2).alias("cost_usd_7d"),
    pl.col("p95_latency_ms").mean().round(0).alias("avg_daily_p95_ms"),
    pl.col("error_rate").mean().round(4).alias("avg_error_rate"),
).sort("cost_usd_7d", descending=True))
assert all(checks.values()), "NB4 Gold incomplete — see FAIL rows above"
print()
print("NB4 complete.")

# %% [markdown]
# ## Giải thích kết quả (NB4)
#
# * **Ba lớp trên storage:** `_lakehouse/bronze/llm_calls_raw`, `_lakehouse/silver/llm_calls`
#   (partition theo `date`) và `_lakehouse/gold/llm_daily_metrics` đều là bảng Delta có
#   `_delta_log/`. Bronze giữ nguyên `raw_json` như lúc ingest để có thể parse lại khi
#   logic Silver thay đổi.
# * **Silver < Bronze:** 200 000 → 190 052 dòng (bỏ 9 948). Generator cố ý chèn các
#   bản retry trùng `request_id`; Silver giữ bản đầu tiên theo `ts`
#   (`ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY ts) = 1`). Không dedup thì
#   mọi chỉ số Gold đều bị thổi phồng: token và chi phí bị đếm ~5% hai lần.
# * **Gold = 7 ngày UTC × 3 model = 21 dòng.** p50 luôn ≤ p95, `cost_usd > 0`,
#   `error_rate` ≈ 0.05 (nằm trong [0, 1]; gồm cả `error` và `rate_limited`).
#   Opus có p50 ≈ 3 000 ms, Sonnet ≈ 1 370 ms, Haiku ≈ 560 ms; Sonnet tốn nhiều tiền
#   nhất dù đơn giá thấp hơn Opus vì có lượng token lớn nhất (giá chỉ là minh họa).
# * **Lỗi múi giờ đã sửa.** Lần chạy đầu cho ra **8 ngày**: 04-01 chỉ có 19 271 dòng và
#   04-08 có 7 915 dòng, trong khi dữ liệu nằm trọn trong 04-01 00:00 → 04-07 23:59 UTC.
#   Nguyên nhân: `CAST(ts AS DATE)` trên `TIMESTAMPTZ` dùng múi giờ phiên DuckDB,
#   mặc định là múi giờ máy (UTC+7), nên ranh giới ngày lệch 7 giờ — ngày đầu thiếu
#   7 giờ, ngày thứ 8 "ảo" chứa 7 giờ cuối. Notebook gốc vẫn PASS (8 ≥ 7) nhưng p95 và
#   cost theo ngày của hai ngày biên sai. Sửa bằng `SET TimeZone = 'UTC'` trước khi
#   dựng Silver; giờ mỗi ngày có ~27 100 dòng. Đây là loại bug Gold mà assertion về số
#   lượng không bắt được — phải kiểm tra phân bố.
