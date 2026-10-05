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
# The provided generator emits valid JSON. This lab dedupes by request_id
# and projects typed columns; malformed JSON fails fast rather than being silently dropped.

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
        -- TIMESTAMPTZ -> DATE follows the session time zone; pin UTC so the
        -- 7 generated UTC days stay 7 Gold dates on any machine.
        CAST(ts AT TIME ZONE 'UTC' AS DATE)         AS date,
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
with pl.Config(tbl_rows=30, tbl_cols=10, tbl_width_chars=160):
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
# ## Kiểm tra đầy đủ hợp đồng Gold
# Đối chiếu từng nhóm bằng Polars, độc lập với câu SQL DuckDB phía trên.
# Quantile dùng nội suy linear tương ứng QUANTILE_CONT. Giá là giả định của lab.

# %%
import math

rates = {"claude-haiku-4-5": (0.8, 4.0), "claude-sonnet-4-6": (3.0, 15.0),
         "claude-opus-4-7": (15.0, 75.0)}
silver_df = pl.from_arrow(DeltaTable(SILVER).to_pyarrow_table())
assert silver_df["request_id"].n_unique() == silver_n
assert (silver_df["ts"].dt.convert_time_zone("UTC").dt.date() == silver_df["date"]).all()
assert gold_df.null_count().sum_horizontal().item() == 0
assert n_models == 3 and gold_df.height == n_dates * n_models
assert gold_df.select(["date", "model"]).n_unique() == gold_df.height
assert gold_df.group_by("date").agg(pl.col("model").n_unique())["model"].to_list() == [3] * n_dates
for row in gold_df.iter_rows(named=True):
    group = silver_df.filter((pl.col("date") == row["date"]) & (pl.col("model") == row["model"]))
    c_in, c_out = rates[row["model"]]
    expected = {
        "p50_latency_ms": group["latency_ms"].quantile(0.5, interpolation="linear"),
        "p95_latency_ms": group["latency_ms"].quantile(0.95, interpolation="linear"),
        "total_prompt_tokens": group["prompt_tokens"].sum(),
        "total_completion_tokens": group["completion_tokens"].sum(),
        "error_rate": (group["status"] != "ok").mean(),
        "cost_usd": (group["prompt_tokens"].sum() * c_in + group["completion_tokens"].sum() * c_out) / 1e6,
    }
    assert all(math.isclose(row[k], v, rel_tol=1e-9, abs_tol=1e-9) for k, v in expected.items())
    assert 0 <= row["error_rate"] <= 1 and row["cost_usd"] > 0
    assert 0 <= row["p50_latency_ms"] <= row["p95_latency_ms"]
for label, location in [("Bronze", BRONZE), ("Silver", SILVER), ("Gold", GOLD)]:
    assert (Path(location) / "_delta_log").is_dir()
    print(f"{label}: {DeltaTable(location).count():,} rows; storage={location}")
print(f"PASS: {n_dates} days x {n_models} models = {gold_df.height} groups; all Gold metrics independently verified")
print(f"Total cost (illustrative USD): {gold_df['cost_usd'].sum():.6f}")
