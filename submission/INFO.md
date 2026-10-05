# Thông tin bài nộp

| Mục | Giá trị |
|---|---|
| Họ tên | Đoàn Tuấn Long (DoanTuanLong) |
| MSSV | 2A202602609 |
| Mã bài | K4-Track02-Day18 — Data Lakehouse Architecture |
| Repo | https://github.com/tlong1610/K4-Track02-Day18-DoanTuanLong-2A202602609-Lakehouse-Lab |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Python | 3.12.6 (venv `.venv`) |
| Hệ điều hành | Windows 11 Pro (10.0.26300), PowerShell |
| Ngày chạy | 2026-10-05 |

## Phiên bản thư viện

`deltalake 1.6.6` · `pyiceberg 0.12.0` · `duckdb 1.5.6` · `polars 1.44.2` · `pyarrow 25.0.1` ·
`numpy 2.5.3` · `jupyterlab 4.6.4` · `jupytext 1.19.6` · `pytest 9.1.1`

## Kết quả kiểm tra (PowerShell, theo README)

| Lệnh | Kết quả |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_lite.py` | 9/9 checks PASS |
| `.\.venv\Scripts\python.exe -m pytest` | 24 passed |
| `.\.venv\Scripts\python.exe scripts/run_all.py` | 8/8 notebooks PASS |

Notebook nộp trong `submission/notebooks/` được sinh bằng `jupytext --to notebook` rồi thực thi
đầu-cuối bằng `jupyter nbconvert --execute`; output được giữ nguyên trong `.ipynb`.

## Số liệu chính so với ngưỡng rubric

| NB | Metric | Đo được | Ngưỡng |
|---|---|---|---|
| 1 | Commit JSON trong `_delta_log/`; ghi `age='thirty'` | 2 commit; bị chặn (`Cannot cast string 'thirty' to value of Int64 type`), version không đổi | ≥ 2; bị chặn |
| 2 | File trước/sau; speedup; files-pruned | 200 → 55; 9–10×; **55×** | ≥ 100; ≥ 3× hoặc ≥ 10× |
| 3 | MERGE; history; `score < 0` sau RESTORE | 50K update + 50K insert; 5 version gồm RESTORE; 0 | ≥ 5 version; 0 |
| 4 | Bronze/Silver; Gold | 200 000 → 190 052; 7 ngày UTC × 3 model | Silver < Bronze; ≥ 7 × 3 |
| 5 | Pruning; field id; spec id | 10×; `latency_millis` id 4; spec {1, 2}, 5 500 dòng đọc được | ≥ 5×; id 4; ≥ 2 |
| 6 | Compaction; clustering; expiry; orphans; checkpoint | 200 → 11 (18×); skip 90%; vacuum thu hồi 16.1 MB, Iceberg 20 → 3 snapshot; 3 orphan xoá + 17 manifest list sweep; checkpoint + `_last_checkpoint` | ≥ 10×; ≥ 50%; 3 snapshot; 3 orphan |
| 7 | Amplification; int8; recall / fidelity; lifecycle bug | 200×; 5.8× nhỏ hơn; 0.904 / 1.000; 0 hit trong bảng vs 8 hit index cũ | ≥ 5×; ≥ 3×; ≥ 0.80 / ≥ 0.95; 0 vs > 0 |
| 8 | Partition `agent_version`; replay; MCP; buckets | 2 partition; 1 578 = 1 578; 5 lượt → 1 lần đọc catalog, `input_required`, task completed; 4 bucket + UNCLASSIFIED bị loại | như rubric |

## Thay đổi so với notebook gốc (giữ nguyên mọi tiêu chí và ngưỡng)

1. **NB1** — cờ "schema enforcement blocked bad write" trước đây hardcode `True`. Giờ lấy từ chính
   cell ghi sai kiểu (bắt exception) và yêu cầu thêm version bảng không đổi sau lần ghi lỗi.
   Thêm cell in danh sách commit trong `_delta_log/` và các action của commit v1 làm bằng chứng.
2. **NB4** — sửa lỗi múi giờ: `CAST(ts AS DATE)` trên `TIMESTAMPTZ` trong DuckDB dùng múi giờ máy
   (UTC+7), làm Gold có 8 "ngày" lệch 7 giờ (ngày đầu thiếu 7 giờ, ngày thứ 8 chỉ có 7 giờ).
   Thêm `SET TimeZone = 'UTC'` trước khi dựng Silver → đúng 7 ngày UTC. Thêm cell kiểm tra
   chất lượng Gold mà bản gốc chưa assert: đủ 3 model mỗi ngày, p50 ≤ p95, `cost_usd > 0`,
   `error_rate ∈ [0, 1]`, đủ 3 lớp trên đĩa.
3. **NB1–NB8** — thêm Markdown cell "Giải thích kết quả" cuối mỗi notebook (mã nguồn `.py` trong
   `notebooks/` đã được đồng bộ).

## Bài nộp

- Notebook đã chạy: [`submission/notebooks/`](notebooks/)
- Screenshots: [`submission/screenshots/`](screenshots/) — render trực tiếp từ output đã lưu trong các `.ipynb`
- Reflection: [`submission/REFLECTION.md`](REFLECTION.md)
- Khai báo AI: [`submission/AI_USAGE.md`](AI_USAGE.md)
- Bonus: [`submission/bonus/ARCHITECTURE.md`](bonus/ARCHITECTURE.md) — Topic A, LLM observability 1B req/ngày;
  PoC [`submission/bonus/poc/`](bonus/poc/) (PII tokenization trước Bronze + retention 7 ngày xoá vật lý,
  7/7 check PASS). Chạy lại PoC: `.\.venv\Scripts\python.exe submission/bonus/poc/poc_pii_retention.py`
