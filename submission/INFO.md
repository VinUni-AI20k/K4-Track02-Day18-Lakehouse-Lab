# Thông tin bài nộp

| | |
|---|---|
| Họ tên | Nguyễn Trường Bảo |
| MSSV | 2A202602540 |
| Mã bài | K4-Track02-Day18 — Data Lakehouse Lab |
| Repo | `K4-Track02-Day18-NguyenTruongBao-2A202602540-Lakehouse-Lab` |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Python | 3.11.9 (venv `.venv`) |
| Hệ điều hành | Windows 11 Pro 10.0.22631 |
| Thư viện chính | deltalake 1.6.6 · pyiceberg 0.12.0 · duckdb 1.5.6 · polars 1.44.2 · pyarrow 25.0.1 · numpy 2.4.6 · pytest 9.1.1 |
| Ngày chạy | 05/10/2026 |
| Bonus | Có — `bonus/ARCHITECTURE.md` (Topic A: LLM observability 1B req/ngày) |

## Kết quả kiểm tra (chạy lại từ `_lakehouse/` trống)

Chạy bằng PowerShell/Git Bash theo hướng dẫn Windows trong README, `PYTHONUTF8=1`:

| Lệnh | Kết quả |
|---|---|
| `python scripts/verify_lite.py` (smoke) | **9/9 PASS** |
| `python scripts/generate_data_lite.py` | 200,000 dòng Bronze, 9,948 bản trùng |
| `python scripts/generate_ai_data.py` | 2,000 docs, 200 blobs, 1,578 trajectory steps |
| `python -m pytest` | **24/24 PASS** |
| `python scripts/run_all.py` | **8/8 PASS** (~38 s) |
| `jupyter nbconvert --execute` cho 8 `.ipynb` | 8/8 chạy hết, không lỗi |

Ghi chú môi trường: trong lần chạy có sandbox, `pytest` mặc định báo `PermissionError` khi tạo thư mục
tạm `%TEMP%\pytest-of-Admin`; chạy với `--basetemp=.pytest_cache/t` thì 24/24 PASS. Đây là quyền truy cập
thư mục tạm của môi trường, không phải lỗi test.

## Nội dung bài nộp

- `notebooks/` — 8 notebook đã thực thi, giữ output; mỗi kết quả chính có một ô **Giải thích kết quả**
  ngay bên dưới.
- `screenshots/` — 17 ảnh render từ chính các notebook đã thực thi (header + code + output + giải thích):
  `nb01_schema`, `nb01_delta_log`, `nb02_optimize`, `nb02_file_stats`, `nb03_history_restore`,
  `nb04_medallion`, `nb05_pruning`, `nb05_schema_spec`, `nb06_compaction_clustering`,
  `nb06_orphans_checkpoint`, `nb06_iceberg_expiry`, `nb07_blob_int8`, `nb07_search`, `nb07_lifecycle`,
  `nb08_trajectories`, `nb08_mcp`, `nb08_provenance`.
- `REFLECTION.md`, `AI_USAGE.md`, `bonus/ARCHITECTURE.md`.

## Thay đổi mã so với đề (chỉ thêm bằng chứng, không hạ ngưỡng)

| File | Thay đổi | Lý do |
|---|---|---|
| `notebooks/01_delta_basics.py` | Cờ "schema enforcement blocked" lấy từ kết quả thật (write ném lỗi **và** version không đổi) thay cho `True` hardcode; thêm mục 6 in danh sách commit `_delta_log/` và nội dung commit JSON | RUBRIC ghi rõ cờ này đang hardcode; CHECKPOINTS yêu cầu nội dung một commit JSON |
| `notebooks/04_medallion.py` | Thêm ô assert phần còn lại của hợp đồng Gold (3 model/ngày, p50 ≤ p95, cost > 0, error_rate ∈ [0, 1]) và in Gold đầy đủ theo (date, model), kèm múi giờ DuckDB | RUBRIC ghi NB4 chưa assert mọi yêu cầu Gold |
| `notebooks/06_maintenance.py` | Tách số parquet "không thấy" thành checkpoint trong `_delta_log/` và orphan thật; in toàn bộ checkpoint và `_last_checkpoint` | Output gốc in "5 files" (3 orphan + 2 checkpoint) và tên checkpoint cũ nhất, dễ đọc sai |

Mọi assertion và ngưỡng gốc giữ nguyên. Các thay đổi đều qua `run_all.py` và pytest.

## Số liệu chính

| NB | Kết quả | Ngưỡng |
|---|---|---|
| 1 | 2 commit JSON; `age='thirty'` bị chặn (version 0 → 0); `tier` thêm bằng merge; 2 nhóm tier | — |
| 2 | 200 file → 55; speedup 13.4×; files-pruned 55× (1/55 file) | ≥ 3× **hoặc** ≥ 10× |
| 3 | MERGE 100K (50K update + 50K insert) 0.07 s; RESTORE 0.01 s; 5 version gồm RESTORE; `score<0` = 0 | ≥ 5 version |
| 4 | Bronze 200,000 → Silver 190,052; Gold 8 ngày × 3 model, mọi kiểm tra Gold PASS | ≥ 7 ngày × 3 model |
| 5 | Pruning 10×; metadata 290 % data; `latency_millis` field_id 4; spec 1 và 2; 5,500 dòng đọc được | ≥ 5× |
| 6 | Compaction 18×; skip 90 %; vacuum thu hồi 16.1 MB; 3 orphan xóa; checkpoint v203; Iceberg 20 → 3 snapshot, quét 17 manifest list | ≥ 10×, ≥ 50 % |
| 7 | Amplification 200×; int8 nhỏ 5.8×; recall@10 0.904; topic fidelity 1.000; 0 vs 8 hit; 8 CDF delete | ≥ 5×, ≥ 3×, ≥ 0.80, ≥ 0.95 |
| 8 | 2 partition `agent_version`; replay v0 = 1,578 step; 5 lượt → 1 lần đọc catalog; `input_required`; task completed; 4 bucket + UNCLASSIFIED (334 dòng bị loại) | — |
