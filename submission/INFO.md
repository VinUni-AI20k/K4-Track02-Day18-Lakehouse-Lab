# Thông tin bài nộp

| Mục | Giá trị |
|---|---|
| Họ và tên | Nguyễn Thị Hạ |
| MSSV | 2A202602536 |
| Mã bài | K4-Track02-Day18 — Lakehouse Lab |
| Repo | `K4-Track02-Day18-NguyenThiHa-2A202602536-Lakehouse-Lab` |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Python | 3.11.8 (venv `.venv`) |
| Hệ điều hành | Windows 11 Pro 10.0.26200 |
| Ngày chạy | 2026-10-05 |

## Phiên bản thư viện đã cài

`deltalake 1.6.6` · `pyiceberg 0.12.0` · `duckdb 1.5.6` · `polars 1.44.2` · `pyarrow 25.0.1` ·
`numpy 2.4.6` · `jupyterlab 4.6.4` · `jupytext 1.19.6` · `pytest 9.1.1`

## Kết quả kiểm tra (chạy từ thư mục gốc repo, Windows, `PYTHONUTF8=1`)

| Lệnh | Kết quả |
|---|---|
| `.venv\Scripts\python.exe scripts\verify_lite.py` | 9/9 checks PASS |
| `.venv\Scripts\python.exe -m pytest` | 24 passed |
| `.venv\Scripts\python.exe scripts\run_all.py` | 8/8 notebooks PASS (~121 s) |

## Cách tạo bài nộp

- `notebooks/*.py` → `.ipynb` bằng `jupytext`, thực thi từ đầu đến cuối bằng
  `python -m nbconvert --to notebook --execute --inplace`, rồi chép vào `submission/notebooks/`.
- Mỗi notebook có thêm cell Markdown **"📝 Giải thích kết quả"** ở cuối, đọc số liệu thực tế của lần chạy.
- `submission/screenshots/*.png` được chụp (headless Chrome) từ các cell output đã lưu trong notebook nộp,
  mỗi notebook ít nhất 1 ảnh.

## Thay đổi so với mã gốc của đề

Chỉ làm kiểm tra **chặt hơn**, không hạ ngưỡng hay bỏ assertion nào:

1. **NB1** — cờ `schema enforcement blocked bad write` trước đây hardcode `True`. Nay lấy từ chính exception
   và kiểm tra version bảng không đổi sau lần ghi lỗi. Thêm cell in danh sách `_delta_log/` và nội dung commit JSON đầu tiên.
2. **NB4** — thêm cell "Gold quality checks" assert p50 ≤ p95, `cost_usd > 0`, `error_rate ∈ [0,1]`,
   mỗi ngày đủ 3 model, Bronze/Silver/Gold đều có `_delta_log/`.
3. Cả 8 notebook — thêm cell Markdown giải thích kết quả.

Khai báo AI: xem [AI_USAGE.md](AI_USAGE.md).
