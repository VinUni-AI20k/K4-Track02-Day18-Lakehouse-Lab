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
p50_le_p95 = (gold_df["p50_latency_ms"] <= gold_df["p95_latency_ms"]).all()
all_positive_cost = (gold_df["cost_usd"] > 0).all()
valid_error_rate = ((gold_df["error_rate"] >= 0.0) & (gold_df["error_rate"] <= 1.0)).all()

print(
    f"\n──── Gold deliverable metrics ────\n"
    f"  Distinct dates:     {n_dates:>3}   (target ≥ 7)\n"
    f"  Distinct models:    {n_models:>3}\n"
    f"  Total Gold rows:    {gold_df.height:>3}   (= dates × models)\n"
    f"  p50 <= p95 latency: {p50_le_p95}\n"
    f"  Cost > 0:           {all_positive_cost}\n"
    f"  0 <= Error Rate <=1:{valid_error_rate}"
)
assert n_dates >= 7, (
    f"Gold has only {n_dates} dates — slide deliverable requires ≥ 7. "
    "Re-run `make data` (the generator spreads across 7 UTC days)."
)
assert p50_le_p95 and all_positive_cost and valid_error_rate, "Gold metric validation failed"

# %% [markdown]
# ## 📝 Báo cáo phân tích và giải thích (NB4)
#
# ### 1. Deduplication ở Silver giải quyết vấn đề nào?
# - **Bản chất của Distributed Ingestion:** Các hệ thống thu thập log/event phân tán (Kafka, Fluentbit, Kinesis, Webhook, client retries) luôn hoạt động theo cơ chế **At-least-once delivery**. Khi xảy ra sự cố mạng chập chờn, gateway timeout hoặc producer retry, một lượt gọi LLM (`request_id`) có thể bị gửi trùng lặp nhiều lần vào tầng Bronze (trong dữ liệu sinh ra, Bronze có 200,000 dòng nhưng chỉ có 190,052 unique `request_id`, tương ứng 9,948 bản ghi trùng lặp).
# - **Trách nhiệm của tầng Silver:** Tầng Silver đảm nhiệm vai trò làm sạch và chuẩn hóa (data cleansing & deduplication). Bằng cách áp dụng window function `ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY ts)`, Silver giữ lại duy nhất 1 bản ghi đầu tiên hợp lệ và loại bỏ các bản sao thừa. Việc này đảm bảo tính **Idempotence** và **Exactly-once semantics** cho downstream analytics, ngăn ngừa việc tính đội chi phí token, sai lệch số lượng người dùng hay số lượt gọi thực tế.
#
# ### 2. Vì sao Dashboard nên đọc bảng Gold thay vì Silver?
# - **Hiệu năng truy vấn (Query Latency):** Bảng Silver lưu trữ chi tiết từng request riêng lẻ (granularity cấp transaction), có thể lên tới hàng chục triệu bản ghi. Nếu dashboard truy vấn trực tiếp Silver, mỗi lần mở trang dashboard hoặc đổi bộ lọc sẽ phải quét toàn bộ bảng và thực hiện aggregate phức tạp (quantile, sum, group by), mất nhiều giây hoặc phút. Bảng Gold đã được tính toán sẵn (pre-aggregated) theo chiều `(date, model)` chỉ gồm 21 dòng (7 ngày × 3 model), giúp dashboard phản hồi tức thì (< 50ms).
# - **FinOps & Chi phí quét dữ liệu:** Các query engine tính phí theo dung lượng quét (ví dụ AWS Athena $5/TB, BigQuery $6.25/TB). Truy vấn Gold chỉ quét vài KB thay vì hàng chục GB ở Silver, tiết kiệm hàng nghìn USD chi phí cloud mỗi tháng.
# - **Tính nhất quán của Metric (Single Source of Truth):** Đặt logic tính p50/p95, error rate và cost model cố định ở pipeline Gold ngăn chặn việc các data analyst hoặc team khác nhau tự viết query với logic percentile/cost sai lệch.
#
# ### 3. Cách tính Error Rate và Chi Phí trong query có phù hợp với dữ liệu đầu vào không?
# - **Error Rate (`AVG(CASE WHEN status <> 'ok' THEN 1.0 ELSE 0.0 END)`):** Hoàn toàn phù hợp. Câu lệnh này ánh xạ trạng thái thành biến nhị phân 0/1 và lấy trung bình theo nhóm, cho ra tỷ lệ lỗi chuẩn xác toán học nằm trong khoảng `[0.0, 1.0]`.
# - **Chi phí (`(SUM(prompt_tokens) * c_in + SUM(completion_tokens) * c_out) / 1e6`):** Hoàn toàn chuẩn xác và khớp với mô hình định giá token thực tế của các nhà cung cấp mô hình (như OpenAI, Anthropic), với đơn giá USD tính trên 1 triệu token phân tách riêng giữa input (prompt) và output (completion). Chi phí luôn dương và tỷ lệ thuận với khối lượng token thực tế.

# %% [markdown]
# ## ✅ Deliverable check
# - [ ] All three tables exist under `_lakehouse/{bronze,silver,gold}/`
# - [ ] Silver has fewer rows than Bronze (dedup worked)
# - [ ] Gold spans ≥ 7 dates × 3 models (slide §8 medallion contract)
# - [ ] Cost & error_rate columns populated and non-zero

# %%
from lakehouse import count_files  # noqa: E402

checks = {
    "bronze exists on storage": Path(BRONZE).exists() and count_files(BRONZE) > 0,
    "silver exists on storage": Path(SILVER).exists() and count_files(SILVER) > 0,
    "gold exists on storage":   Path(GOLD).exists() and count_files(GOLD) > 0,
    "silver dedup reduced rows": silver_n < bronze_n,
    "gold spans ≥ 7 dates":     n_dates >= 7,
    "gold covers 3 models":     n_models == 3,
    "p50 <= p95 latency":       p50_le_p95,
    "cost is positive":         all_positive_cost,
    "error rate in [0, 1]":     valid_error_rate,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "NB4 incomplete — see FAIL rows above"
print("\nNB4 complete.")
