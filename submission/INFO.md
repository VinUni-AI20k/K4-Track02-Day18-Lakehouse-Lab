# Thông tin bài nộp

- **Họ tên:** Tran Manh Tung
- **MSSV:** 2A202602879
- **Mã bài:** K4-Track02-Day18
- **Repo:** `K4-Track02-Day18-TranManhTung-2A202602879-Lakehouse-Lab`
- **Đường chạy:** Lightweight (delta-rs, PyIceberg, DuckDB, Polars) cho NB1–NB8
- **Python:** 3.11.9
- **Hệ điều hành:** Windows, PowerShell
- **Ngày thực hiện:** 2026-10-05

Notebook trong `notebooks/` giữ output chạy; phần phân tích và giải thích đã được thêm vào cuối từng notebook trong thư mục nộp. Ảnh kết quả sẽ được bổ sung trong `screenshots/`.

## Kiểm tra môi trường và notebook

- Smoke test: **9/9 PASS**.
- Pytest: **24/24 PASS**.
- Runner: **8/8 notebook PASS** với `LAKEHOUSE_ROOT` tạm riêng để tránh đụng SQLite catalog đang mở trong các kernel Jupyter.
- Các bản notebook trong `submission/notebooks/` giữ output đã chạy và có phần giải thích ở cuối từng file.
