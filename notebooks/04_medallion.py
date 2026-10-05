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

silver_table = DeltaTable(SILVER).to_pyarrow_table()
silver_df = pl.from_arrow(silver_table)
silver_n = silver_table.num_rows
silver_unique_requests = silver_df["request_id"].n_unique()
silver_statuses = set(silver_df["status"].unique().to_list())
silver_tokens_nonnegative = silver_df.select(
    ((pl.col("prompt_tokens") >= 0) & (pl.col("completion_tokens") >= 0)).all()
).item()
print(f"Silver rows: {silver_n:,}  (Bronze {bronze_n:,} → dedup dropped {bronze_n - silver_n:,})")
print(f"Unique Silver request_id: {silver_unique_requests:,} / {silver_n:,}")
print("Silver status counts:")
print(silver_df.group_by("status").len().sort("status"))
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

con.register("silver", silver_table)
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
gold_evidence = gold_df.select(
    "date", "model", "p50_latency_ms", "p95_latency_ms", "error_rate", "cost_usd"
)
with pl.Config(tbl_rows=30, tbl_cols=8):
    print(gold_evidence)

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

storage_evidence = pl.DataFrame({
    "layer": ["Bronze", "Silver", "Gold"],
    "rows": [bronze_n, silver_n, gold_df.height],
    "path": [
        (Path("_lakehouse") / Path(p).relative_to(Path(BRONZE).parents[1])).as_posix()
        for p in (BRONZE, SILVER, GOLD)
    ],
    "delta_log": [(Path(p) / "_delta_log").exists() for p in (BRONZE, SILVER, GOLD)],
})
print("\nStorage evidence:")
print(storage_evidence)

print("\nGold metric ranges:")
print(gold_df.select(
    pl.col("p50_latency_ms").min().alias("min_p50_ms"),
    pl.col("p95_latency_ms").max().alias("max_p95_ms"),
    pl.col("cost_usd").min().alias("min_cost_usd"),
    pl.col("cost_usd").max().alias("max_cost_usd"),
    pl.col("error_rate").min().alias("min_error_rate"),
    pl.col("error_rate").max().alias("max_error_rate"),
))

# Independently recompute the two business formulas from Silver so the checks
# validate correctness, not merely non-null/range constraints.
rates = pl.DataFrame({
    "model": ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"],
    "c_in": [0.80, 3.00, 15.00],
    "c_out": [4.00, 15.00, 75.00],
})
cost_formula_matches = (
    gold_df.join(rates, on="model")
    .with_columns((
        pl.col("total_prompt_tokens") * pl.col("c_in") / 1e6
        + pl.col("total_completion_tokens") * pl.col("c_out") / 1e6
    ).alias("expected_cost_usd"))
    .select(((pl.col("cost_usd") - pl.col("expected_cost_usd")).abs() < 1e-9).all())
    .item()
)
expected_error_rates = silver_df.group_by(["date", "model"]).agg(
    (pl.col("status") != "ok").mean().alias("expected_error_rate")
)
error_formula_matches = (
    gold_df.join(expected_error_rates, on=["date", "model"])
    .select(((pl.col("error_rate") - pl.col("expected_error_rate")).abs() < 1e-12).all())
    .item()
)

gold_checks = {
    "bronze, silver, gold are Delta tables": all((Path(p) / "_delta_log").exists() for p in (BRONZE, SILVER, GOLD)),
    "silver dedup dropped rows": silver_n < bronze_n,
    "silver request_id is unique": silver_unique_requests == silver_n,
    "silver status matches error-rate rule": silver_statuses == {"ok", "rate_limited", "error"},
    "silver token counts are non-negative": silver_tokens_nonnegative,
    "gold covers >=7 dates x 3 models": (
        n_dates >= 7
        and n_models == 3
        and gold_df.select("date", "model").unique().height == n_dates * n_models
    ),
    "gold has expected models": set(gold_df["model"].to_list()) == {
        "claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"
    },
    "p50 <= p95": gold_df.select((pl.col("p50_latency_ms") <= pl.col("p95_latency_ms")).all()).item(),
    "cost_usd positive": gold_df.select((pl.col("cost_usd") > 0).all()).item(),
    "error_rate in [0, 1]": gold_df.select(pl.col("error_rate").is_between(0, 1).all()).item(),
    "cost formula matches token totals": cost_formula_matches,
    "error-rate formula matches Silver": error_formula_matches,
}
for label, ok in gold_checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
assert all(gold_checks.values()), "NB4 incomplete — see FAIL rows above"
print("\nNB4 complete.")

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] All three tables exist under `_lakehouse/{bronze,silver,gold}/`
# - [ ] Silver has fewer rows than Bronze (dedup worked)
# - [ ] Silver request_id is unique; statuses/tokens satisfy metric assumptions
# - [ ] Gold spans ≥ 7 dates × 3 models (slide §8 medallion contract)
# - [ ] p50 ≤ p95, cost_usd > 0, and error_rate is in [0, 1]

# %% [markdown]
# ## Nhận xét kết quả
#
# Bronze giữ 200.000 sự kiện thô để có thể replay/audit. Silver parse JSON thành cột
# có kiểu và dedup theo request_id, loại 9.948 retry trùng; nếu không dedup, cùng một
# request bị đếm nhiều lần sẽ làm sai traffic, token, cost, latency và error rate.
# Silver còn 190.052 dòng và 190.052 request_id duy nhất.
#
# Gold tạo đủ 24 tổ hợp (8 ngày × 3 model). Dashboard đọc Gold vì câu hỏi vận hành
# cần vài chục dòng tổng hợp thay vì scan gần 200K request; định nghĩa metric cũng
# được dùng nhất quán. p50/p95 lấy quantile của latency theo từng date/model.
# error_rate là trung bình indicator status != "ok" trên các request đã dedup, nên
# cả error và rate_limited đều được tính là request không thành công. Cách này phù
# hợp với ba status mà generator tạo. cost_usd cộng input/output token
# rồi nhân đơn giá riêng của model trên một triệu token. Công thức phù hợp với schema
# đầu vào, nhưng COST_TABLE chỉ là giá minh họa của lab, không phải giá production.
