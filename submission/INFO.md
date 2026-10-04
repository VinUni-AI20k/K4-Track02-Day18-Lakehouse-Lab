# Thông tin bài nộp — K4-Track02-Day18 Lakehouse Lab

| Mục | Giá trị |
|---|---|
| Họ tên | Lò Văn Long |
| MSSV | 2A202602541 |
| Mã bài | K4-Track02-Day18 |
| Repo | https://github.com/getlmt/K4-Track02-Day18-LoVanLong-2A202602541-Lakehouse-Lab |
| Đường chạy | **Lightweight** cho cả 8 notebook (`deltalake` + `pyiceberg` + DuckDB + Polars); **không** dùng Spark cho NB1–NB4 |
| Hệ điều hành | Windows 10 Home Single Language (10.0.19045), PowerShell |
| Python | 3.11.9 (venv `.venv`, cài bằng `pip install -r requirements.txt`) |
| Phiên bản thư viện | deltalake 1.6.6 · pyiceberg 0.12.0 (pyiceberg-core 0.10.1) · duckdb 1.5.6 · polars 1.44.2 · pyarrow 25.0.1 · numpy 2.4.6 · jupyterlab 4.6.4 · jupytext 1.19.5 · nbconvert 7.17.1 · pytest 9.1.1 |
| Ngày chạy | 04/10/2026 |

## Cách thực thi notebook

1. Xóa `_lakehouse/`, sinh lại dữ liệu bằng `scripts/generate_data_lite.py` và `scripts/generate_ai_data.py`.
2. `jupytext --to notebook notebooks/0*.py` → `.ipynb`.
3. Thực thi từng notebook bằng Jupyter kernel `python3` của `.venv`:
   `jupyter nbconvert --to notebook --execute --inplace <nb>.ipynb` (chạy từ trên xuống, lưu output).
4. Chép 8 file `.ipynb` đã chạy vào `submission/notebooks/` (không có `_setup.ipynb`).

## Kết quả kiểm tra (log đầy đủ: [logs/reproducibility.txt](logs/reproducibility.txt))

| Kiểm tra | Kết quả |
|---|---|
| Smoke test `scripts/verify_lite.py` | 9/9 PASS |
| `python -m pytest` | 24 passed |
| `scripts/run_all.py` | 8/8 PASS |

## Thay đổi so với mã đề bài

Chỉ **thêm** cell vào `notebooks/0*.py` (`git diff` chỉ có dòng thêm, 0 dòng bị xóa): các cell
"🔎 Bằng chứng bổ sung" (chỉ đọc hoặc chạy trên bảng scratch riêng) và một cell
"📝 Giải thích kết quả" cho mỗi notebook. Không sửa hay xóa assertion, không hạ ngưỡng.

## Screenshots (`submission/screenshots/`)

Ảnh được render từ chính các `.ipynb` đã thực thi (nbconvert → HTML → Chrome headless), không chỉnh sửa output.

| Notebook | Ảnh |
|---|---|
| NB1 | `nb01_delta_log.png` (`_delta_log/` + nội dung commit JSON), `nb01_schema_enforcement.png` |
| NB2 | `nb02_optimize.png` (trước/sau, speedup, pruning), `nb02_zorder_stats.png` (min/max từng file) |
| NB3 | `nb03_history_restore.png` |
| NB4 | `nb04_gold.png` (Gold đầy đủ + check), `nb04_timezone_status.png` |
| NB5 | `nb05_iceberg.png`, `nb05_fieldid_specs.png` |
| NB6 | `nb06_compaction_vacuum.png`, `nb06_orphans_checkpoint.png`, `nb06_iceberg_expiry.png` |
| NB7 | `nb07_vectors.png`, `nb07_search_lifecycle.png` |
| NB8 | `nb08_agents_mcp.png`, `nb08_provenance_erasure.png` |
| Reproducibility | `repro_tests.png` |

## Các phát hiện đáng chú ý trên máy mình

- **NB1:** enforcement của delta-rs 1.6.6 là "ép kiểu được thì ghi": `'31'` → 31, `1.5` → 1 (bị cắt âm thầm); chỉ `'thirty'` bị chặn.
- **NB4:** Gold có 8 ngày thay vì 7 vì DuckDB cắt `date` theo múi giờ máy (`Asia/Bangkok`, UTC+7); theo UTC là 7 ngày.
- **NB6:** "0 B" là lỗi hiển thị (đường dẫn tương đối); "5 files cannot see" gồm 3 orphan + 2 checkpoint tự động;
  `vacuum(full=True)` của deltalake 1.6.6 có tìm thấy orphan, chế độ mặc định thì không.

## Bonus

Topic **D — Multimodal RAG trên 10 triệu văn bản pháp lý**: [bonus/ARCHITECTURE.md](bonus/ARCHITECTURE.md)
(6 trang A4 khi render), kèm PoC [bonus/poc/reproducible_retrieval_poc.ipynb](bonus/poc/reproducible_retrieval_poc.ipynb)
(chạy từ gốc repo: `python submission/bonus/poc/reproducible_retrieval_poc.py`; kết quả 50/50 citation replay đúng từ tag).

Khai báo sử dụng AI: [AI_USAGE.md](AI_USAGE.md).
