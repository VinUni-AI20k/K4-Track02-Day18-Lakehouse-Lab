# Thông tin bài nộp — K4-Track02-Day18 Lakehouse Lab

| Mục | Giá trị |
|---|---|
| Họ tên | Bùi Thị Thu Uyên |
| MSSV | 2A202602613 |
| Mã bài | K4-Track02-Day18 |
| Repo | https://github.com/Ujandok/K4-Track02-Day18-BuiThiThuUyen-2A202602613-Lakehouse-Lab |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Python | 3.11.7 (venv `.venv` tạo bằng `uv venv --python 3.11`) |
| Hệ điều hành | Windows 11 Home Single Language 10.0.26200 (chạy bằng PowerShell, không dùng WSL/`make`) |
| Thư viện | `deltalake` 1.6.6 · `pyiceberg` 0.12.0 · `duckdb` 1.5.6 · `polars` 1.44.2 · `pyarrow` 25.0.1 · `numpy` 2.4.6 |
| Ngày chạy | 05/10/2026 |

## Kết quả kiểm tra (chạy lại từ `_lakehouse/` trống)

| Lệnh (PowerShell tương đương `make`) | Kết quả | Log |
|---|---|---|
| `scripts/verify_lite.py` (`make smoke`) | **9/9 PASS** | [evidence/smoke.txt](evidence/smoke.txt) |
| `scripts/generate_data_lite.py` + `generate_ai_data.py` | 200,000 dòng Bronze; 2,000 docs, 200 blobs, 1,578 steps | [evidence/generate_data.txt](evidence/generate_data.txt) |
| `python -m pytest` (`make test`) | **24/24 PASS** | [evidence/pytest.txt](evidence/pytest.txt) |
| `scripts/run_all.py` (`make run-all`) | **8/8 PASS** | [evidence/run_all.txt](evidence/run_all.txt) |

8 notebook trong [notebooks/](notebooks/) được thực thi từ đầu đến cuối bằng Jupyter kernel của `.venv`
(`jupyter nbconvert --execute`), giữ nguyên output. Mỗi notebook có thêm ô **"🔎 Giải thích kết quả"** ngay trước
ô kiểm tra cuối.

## Tóm tắt số liệu theo rubric

| NB | Tiêu chí chính | Đo được |
|---|---|---|
| 1 | `_delta_log/` JSON · chặn ghi sai kiểu · `tier` qua merge | 2 commit JSON · `Cast error: Cannot cast string 'thirty' to value of Int64 type`, v0 → v0 · có cột `tier`, 2 nhóm |
| 2 | ≥ 100 file · speedup ≥ 3× **hoặc** pruning ≥ 10× | 200 → 55 file · speedup 8.1× · pruning 55× |
| 3 | MERGE 100K · history ≥ 5 có RESTORE · `score<0` = 0 | 50K update + 50K insert · 5 version (v4 RESTORE) · 50 → 0 |
| 4 | Silver < Bronze · Gold ≥ 7 ngày × 3 model | 190,052 < 200,000 · 7 × 3 = 21 dòng, p50 ≤ p95, cost > 0, error_rate 0.045–0.062 |
| 5 | pruning ≥ 5× trên `ts` · field_id giữ · ≥ 2 spec | 10× · `latency_millis` id 4 · spec [1, 2], đọc đủ 5,500 dòng |
| 6 | compaction ≥ 10× · skip ≥ 50% · expiry · orphans · checkpoint | 18× · 90% · thu hồi 16.1 MB, Iceberg 20 → 3 snapshot · 3 orphan Delta + 17 manifest list · v203 checkpoint |
| 7 | amplification ≥ 5× · int8 ≥ 3× · recall ≥ 0.80 · fidelity ≥ 0.95 · lifecycle bug | 200× · 5.8× · 0.904 · 1.000 · 0 hit trong bảng / 8 hit ở index cũ |
| 8 | partition `agent_version` · pin version · MCP mô phỏng · 4 bucket | 2 partition · replay 1,578 = 1,578 · 5 lượt → 1 lần đọc catalog, `input_required`, task completed · 4 bucket + UNCLASSIFIED (334 dòng bị loại) |

## Thay đổi so với mã đề bài

Không hạ ngưỡng và không bỏ assertion nào. Các thay đổi chỉ làm phép kiểm tra **chặt hơn** hoặc sửa chỗ đo sai.
Mã nguồn đã sửa nằm trong `notebooks/*.py`.

| Notebook | Thay đổi | Lý do |
|---|---|---|
| NB1 | Thêm ô in `_delta_log/` và nội dung commit v0/v1. Thay cờ hardcode `True` bằng `bad_write_blocked` cộng điều kiện version không đổi | Rubric yêu cầu bằng chứng log; cờ cũ không chứng minh gì |
| NB3 | In số dòng `score<0` ở v3 trước RESTORE và đọc lại v3 sau RESTORE | Chứng minh RESTORE rollback thật mà vẫn giữ lịch sử |
| NB4 | `SET TimeZone = 'UTC'` cho DuckDB; thêm ô kiểm tra đầy đủ các yêu cầu Gold | Múi giờ máy (UTC+7) làm 7 ngày UTC thành 8 ngày "cụt", Gold phụ thuộc người chạy; notebook gốc chưa assert hết yêu cầu Gold |
| NB6 | Resolve đường dẫn tương đối của `vacuum()`; chỉ đếm data file (bỏ checkpoint tự động trong `_delta_log/`); Job 5 kiểm tra đúng checkpoint mới và `_last_checkpoint.version` | Bản gốc in `0 B`, "5 orphan" (thực tế 3), và check checkpoint PASS nhờ checkpoint tự động v99 |
| NB8 | Đo số dòng subject còn đọc được ở version cũ bằng time travel | Notebook gốc chỉ khẳng định, chưa đo |

## Screenshots

Ảnh trong [screenshots/](screenshots/) được render từ output đã lưu trong `submission/notebooks/*.ipynb`
(xuất HTML bằng nbconvert, chụp full-page bằng Microsoft Edge headless; ẩn code, giữ các ô kết quả chính và ô PASS/FAIL).

| Ảnh | Nội dung |
|---|---|
| [nb01_delta_log.png](screenshots/nb01_delta_log.png) | `_delta_log/`, commit JSON v0, ghi sai kiểu bị chặn, `metaData` v1 có `tier` |
| [nb02_optimize.png](screenshots/nb02_optimize.png) | Số file trước/sau, speedup, min/max `user_id` từng file, pruning ratio |
| [nb03_history_restore.png](screenshots/nb03_history_restore.png) | MERGE metrics, time travel, RESTORE, history sau RESTORE |
| [nb04_gold.png](screenshots/nb04_gold.png) | Bronze/Silver, bảng Gold 21 dòng, kiểm tra chất lượng Gold |
| [nb05_iceberg_catalog.png](screenshots/nb05_iceberg_catalog.png) | Partition spec, pruning, cây metadata, field ID, partition evolution |
| [nb06_maintenance.png](screenshots/nb06_maintenance.png) | Số trước/sau của các job, orphan, checkpoint, Iceberg expiry + sweep |
| [nb07_vectors_multimodal.png](screenshots/nb07_vectors_multimodal.png) | Amplification, int8, recall/fidelity, lifecycle bug, CDF |
| [nb08_agents_provenance.png](screenshots/nb08_agents_provenance.png) | Trajectory medallion, pin version, MCP mô phỏng, provenance, xóa subject |

Reflection: [REFLECTION.md](REFLECTION.md) · Khai báo AI: [AI_USAGE.md](AI_USAGE.md)
