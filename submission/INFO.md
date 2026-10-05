# K4-Track02-Day18 — Thông tin bài nộp

| Mục | Giá trị |
|---|---|
| Họ tên | Vũ Minh Điềm |
| MSSV | 2A202602858 |
| Mã bài | K4-Track02-Day18 — Lakehouse Lab |
| Đường chạy | **Lightweight** cho cả 8 notebook (không dùng Spark cho NB1–NB4) |
| Python | 3.13.12 (venv `.venv`) |
| Hệ điều hành | Windows 11 Home 10.0.26200, PowerShell |
| Thư viện chính | deltalake 1.6.6 · pyiceberg 0.12.0 · duckdb 1.5.6 · polars 1.44.2 · pyarrow 25.0.1 · numpy 2.5.3 |

## Kết quả kiểm tra (05/10/2026)

| Lệnh (PowerShell) | Kết quả |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_lite.py` | 9/9 checks PASS |
| `.\.venv\Scripts\python.exe -m pytest` | 24/24 PASS |
| `.\.venv\Scripts\python.exe scripts/run_all.py` | 8/8 notebook PASS (90.3 s) |

## Số liệu chính

| NB | Kết quả | Ngưỡng |
|---|---|---|
| 1 | 2 commit JSON trong `_delta_log/`; ghi `age='thirty'` bị chặn (Cast error); `tier` thêm bằng `schema_mode="merge"` | — |
| 2 | 200 → 55 file; speedup 8.5×; pruning 55× | ≥ 3× hoặc ≥ 10× |
| 3 | MERGE 100K (50K update + 50K insert); RESTORE → `score<0` = 0; 5 version gồm RESTORE | ≥ 5 version |
| 4 | Bronze 200,000 → Silver 190,052; Gold 8 ngày × 3 model | Silver < Bronze; ≥ 7 × 3 |
| 5 | Pruning 10× khi lọc trên `ts`; `latency_millis` giữ field_id 4; spec 1 & 2 cùng tồn tại | ≥ 5× |
| 6 | Compaction 18×; skip 90%; vacuum thu hồi 16.1 MB; Iceberg 20 → 3 snapshot + quét 17 manifest list; 3 orphan xoá; checkpoint | ≥ 10×, ≥ 50% |
| 7 | Amplification 200×; int8 nhỏ 5.8×, recall@10 0.904, topic fidelity 1.000; lifecycle bug 0 vs 8 hit | ≥ 5×, ≥ 3×, ≥ 0.80, ≥ 0.95 |
| 8 | Silver partition theo `agent_version`; replay v0 = 1,578 step; 5 turn → 1 catalog read; 4 bucket + UNCLASSIFIED | — |

## Ghi chú về bản nộp

- `submission/notebooks/` chứa 8 `.ipynb` đã thực thi bằng `jupyter nbconvert --execute`, giữ nguyên output.
  Mỗi notebook có thêm một Markdown cell **"Giải thích kết quả"** ở cuối.
- Hai cell code được bổ sung (không sửa cell gốc):
  - NB1: liệt kê `_delta_log/` và in nội dung commit `00000000000000000000.json`.
  - NB4: kiểm tra Gold (≥ 7 ngày × 3 model, p50 ≤ p95, `cost_usd > 0`, `error_rate ∈ [0,1]`), vì notebook gốc chưa assert đủ.
- `submission/screenshots/` là ảnh chụp full-page của từng notebook đã chạy (export HTML bằng nbconvert, chụp bằng Edge headless).
- Phạm vi sử dụng AI: xem [AI_USAGE.md](AI_USAGE.md).

## Bonus

- [bonus/ARCHITECTURE.md](bonus/ARCHITECTURE.md): Topic A, LLM observability 1B req/ngày.
- PoC: [bonus/poc/pii_retention_poc.py](bonus/poc/pii_retention_poc.py), gồm token hoá PII tại Bronze và retention xoá bytes thật trên Iceberg; 6/6 check PASS ([output](bonus/poc/OUTPUT.txt)).
