# Thông tin bài nộp

- **Họ và tên:** Đinh Ngọc Đức
- **MSSV:** 2A202602935
- **Mã bài:** K4-Track02-Day18
- **Đường chạy:** Lightweight (`deltalake`/delta-rs + PyIceberg + DuckDB), không dùng Spark/JVM
- **Python:** 3.11.9
- **Hệ điều hành:** Windows 10.0.19045 (64-bit)
- **Ngày xác minh:** 05/10/2026, múi giờ Asia/Ho_Chi_Minh (UTC+7)

## Phiên bản chính

| Gói | Phiên bản |
|---|---:|
| deltalake | 1.6.6 |
| pyiceberg | 0.12.0 |
| duckdb | 1.5.6 |
| polars | 1.44.2 |
| pyarrow | 25.0.1 |
| numpy | 2.4.6 |
| jupyterlab | 4.6.4 |
| jupytext | 1.19.5 |

## Kết quả xác minh

- Smoke test: **9/9 PASS**.
- Pytest: **24/24 PASS**.
- Lightweight notebooks: **8/8 PASS**.
- Tám notebook trong `submission/notebooks/` được thực thi bằng `.venv` và giữ output thật.
