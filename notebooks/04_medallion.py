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
# ## ✅ Deliverable check
# - [ ] All three tables exist under `_lakehouse/{bronze,silver,gold}/`
# - [ ] Silver has fewer rows than Bronze (dedup worked)
# - [ ] Gold spans ≥ 7 dates × 3 models (slide §8 medallion contract)
# - [ ] Cost & error_rate columns populated and non-zero

# %%
# Explicit Gold-quality gate: the cells above only assert Silver < Bronze and
# ≥ 7 dates, so check every rubric requirement for Gold here.
gold_q = gold_df.with_columns(pl.col("error_rate").cast(pl.Float64))
per_model_dates = gold_q.group_by("model").agg(pl.col("date").n_unique().alias("n_dates"))
layers = {name: Path(p, "_delta_log").exists() for name, p in
          [("bronze", BRONZE), ("silver", SILVER), ("gold", GOLD)]}
checks = {
    "bronze/silver/gold all on disk":     all(layers.values()),
    "silver < bronze (dedup)":            silver_n < bronze_n,
    "3 models in Gold":                   n_models == 3,
    "every model has ≥ 7 dates":          per_model_dates["n_dates"].min() >= 7,
    "p50 ≤ p95 on every row":             (gold_q["p50_latency_ms"] <= gold_q["p95_latency_ms"]).all(),
    "cost_usd > 0 on every row":          (gold_q["cost_usd"] > 0).all(),
    "error_rate in [0, 1] on every row":  gold_q["error_rate"].is_between(0, 1).all(),
    "no null metrics":                    gold_q.null_count().sum_horizontal()[0] == 0,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print("\nRows per date (first/last date are partial if the session timezone is not UTC):")
print(con.sql("""SELECT date, count(*) AS silver_rows FROM silver
                 GROUP BY 1 ORDER BY 1""").fetchall())
session_tz = con.sql("SELECT current_setting('TimeZone')").fetchone()[0]
print(f"DuckDB session TimeZone: {session_tz}")
assert all(checks.values()), "NB4 Gold incomplete — see FAIL rows above"
print("\nNB4 complete.")

# %% [markdown]
# ## 📝 Phân tích kết quả (NB4)
#
# - **3 tầng trên storage:** `_lakehouse/bronze/llm_calls_raw`, `_lakehouse/silver/llm_calls`,
#   `_lakehouse/gold/llm_daily_metrics` đều là bảng Delta có `_delta_log/` (check `bronze/silver/gold all on disk`).
# - **Silver < Bronze:** 200,000 → **190,052** dòng; dedup theo `request_id` (giữ bản ghi sớm nhất bằng
#   `ROW_NUMBER()`) loại **9,948** bản retry trùng — khớp đúng số duplicate mà generator đã seed.
# - **Gold:** 24 dòng = **8 ngày × 3 model**, mỗi model có ≥ 7 ngày. Cell kiểm tra mới assert thêm
#   `p50 ≤ p95`, `cost_usd > 0`, `error_rate ∈ [0, 1]` và không null — notebook gốc chưa assert các điều này.
#   Đọc số: haiku p50 ≈ 560 ms, sonnet ≈ 1.38 s, opus ≈ 3.0 s; p95 ≈ 2× p50; error_rate ≈ 5% đồng đều;
#   sonnet tốn nhiều tiền nhất mỗi ngày vì volume token lớn nhất, dù đơn giá thấp hơn opus (giá minh họa).
# - **Vì sao 8 ngày mà không phải 7?** Generator sinh 7 ngày UTC, nhưng `CAST(ts AS DATE)` trong DuckDB dùng
#   TimeZone của session (`Asia/Bangkok`, UTC+7). Ngày 04-01 chỉ có 19,271 dòng và 04-08 có 7,915 dòng —
#   hai ngày "một phần". Bài học: phân vùng theo ngày phải cố định timezone (ví dụ `SET TimeZone='UTC'`),
#   nếu không cùng một code chạy trên hai máy sẽ ra Gold khác nhau.

# %% [markdown]
# ## ❓ Trả lời câu hỏi (mục 3.4)
#
# **1. Dedup ở Silver giải quyết vấn đề nào?**
# Bronze có 200,000 dòng nhưng chỉ 190,052 `request_id` duy nhất: 9,948 dòng là bản ghi lặp do retry/gửi lại
# (9,687 request_id xuất hiện ≥ 2 lần). Không dedup thì mọi metric ở Gold bị đếm trùng: số request, tổng token,
# chi phí bị thổi lên ~5%, và latency/error_rate bị lệch theo các lần retry. Silver dùng `ROW_NUMBER() OVER
# (PARTITION BY request_id ORDER BY ts)` để giữ đúng một dòng/request (bản sớm nhất), biến Silver thành "một sự thật"
# cho mọi consumer.
#
# **2. Vì sao dashboard đọc Gold?**
# Gold đã tổng hợp sẵn 190K dòng thành 24 dòng (ngày × model), partition theo `date` và Z-order theo `model`.
# Dashboard chỉ đọc vài KB thay vì quét + parse JSON của cả bảng, nên nhanh và rẻ; và mọi dashboard dùng chung một
# định nghĩa p50/p95/cost/error_rate thay vì mỗi người tự viết query trên Bronze và ra số khác nhau.
#
# **3. Cách tính error rate và chi phí có phù hợp với dữ liệu đầu vào không?** — Hợp lý cho lab, nhưng có hạn chế
# mình kiểm tra trực tiếp trên Silver:
# - `error_rate = AVG(status <> 'ok')` gộp cả `error` (3,757) lẫn `rate_limited` (5,683) → ~5%. Hợp lý nếu "lỗi" là
#   mọi request không thành công, nhưng nên tách hai loại vì nguyên nhân khác nhau (lỗi model vs. hết quota).
#   Nếu `status` NULL, `NULL <> 'ok'` rơi vào nhánh ELSE → bị đếm là thành công; dữ liệu này không có NULL, nhưng
#   production nên dùng `status IS DISTINCT FROM 'ok'`.
# - `cost_usd` tính cho *mọi* request, kể cả request lỗi: trong dữ liệu sinh, request `error`/`rate_limited` vẫn có
#   ~1,000 completion token trung bình. Thực tế request bị rate-limit thường không sinh output token nên không bị tính
#   tiền → cost ở đây bị **ước lượng cao**. Ngoài ra đơn giá là giá minh họa.
# - Dedup giữ bản ghi *sớm nhất*; với retry thật, bản cuối cùng thường mới là kết quả cuối (ví dụ lần 1 lỗi, lần 2 ok),
#   nên giữ bản đầu có thể làm error_rate cao hơn thực tế.
# - Ngày được tính theo TimeZone của session DuckDB (`Asia/Bangkok`) chứ không theo UTC → 8 ngày, trong đó 04-01 và
#   04-08 chỉ có một phần dữ liệu; nên `SET TimeZone='UTC'` trước khi tạo cột `date`.
