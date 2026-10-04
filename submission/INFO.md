# K4-Track02-Day18 — Thông tin bài nộp (Lakehouse Lab)

## 1. Thông tin học viên & Repository
- **Họ và tên:** Đào Thanh Trường
- **MSSV:** 2A202602683
- **Tài khoản GitHub:** kenproo
- **Mã bài lab:** `K4-Track02-Day18`
- **Tên repository bài nộp:** `K4-Track02-Day18-DaoThanhTruong-2A202602683-Lakehouse-Lab`
- **URL repo GitHub:** `https://github.com/kenproo/K4-Track02-Day18-DaoThanhTruong-2A202602683-Lakehouse-Lab`
- **Commit SHA:** `091032501de6648d6fa0a053f7b1963f1707768e`

## 2. Môi trường thực thi
- **Hệ điều hành:** Windows 11 Pro (x86_64)
- **Phiên bản Python:** Python 3.11.16 (quản lý qua `uv`)
- **Đường chạy (Execution Path):** Lightweight Path (Offline, Zero-JVM, Native Wheels)
- **Phiên bản các thư viện nòng cốt:**
  - `deltalake == 1.6.6` (delta-rs 1.x)
  - `pyiceberg == 0.12.0` (Apache Iceberg REST / SQLite Catalog)
  - `duckdb == 1.5.6` (In-process columnar SQL engine & Vector Similarity)
  - `polars == 1.44.2`
  - `pyarrow == 25.0.1`
  - `pytest == 9.1.1`
  - `jupyterlab == 4.6.4` / `jupytext == 1.19.5`

## 3. Tổng kết trạng thái kiểm thử (Verification Status)
- **Smoke test (`verify_lite.py`):** 9/9 PASS (Delta read/write, history, time travel, CDF, maintenance, Iceberg catalog & planning, DuckDB vector).
- **Pytest test suite (`pytest`):** 24/24 PASS (100% green).
- **Headless Notebook Runner (`run_all.py`):** 8/8 PASS trong 63.3s.
- **Notebooks đã thực thi có output đầy đủ:** 8/8 file `.ipynb` tại `submission/notebooks/`.
- **Bằng chứng hình ảnh kết quả:** 8 ảnh tại `submission/screenshots/` (`nb01_delta_log.png` đến `nb08_agents_provenance.png`).
- **Phần Bonus Architecture Brief:** Đã hoàn thành đề án kiến trúc cấp cao tại `submission/bonus/ARCHITECTURE.md` (chọn Topic A: LLM Observability 1B req/ngày với FinOps ≤ $5K/tháng) kèm mã PoC tại `submission/bonus/poc/`.
