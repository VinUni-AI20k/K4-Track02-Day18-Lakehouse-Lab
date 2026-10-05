# Thông tin bài nộp

| | |
|---|---|
| Họ tên | Nguyễn Phúc Bảo |
| MSSV | 2A202602925 |
| Mã bài | K4-Track02-Day18 — Lakehouse Lab |
| Repo | https://github.com/PhucBao1/K4-Track02-Day18-NguyenPhucBao-2A202602925-Lakehouse-Lab |
| Đường chạy | **Lightweight** cho cả 8 notebook (không dùng Spark cho NB1–NB4) |
| Python | 3.12.4 (venv `.venv`, cài bằng `uv pip install -r requirements.txt`) |
| Hệ điều hành | Windows 11 Home Single Language 10.0.26200, PowerShell |
| Thư viện chính | deltalake 1.6.6 · pyiceberg 0.12.0 · duckdb 1.5.6 · polars 1.44.2 · pyarrow 25.0.1 · numpy 2.5.3 (xem [`evidence/package_versions.txt`](evidence/package_versions.txt)) |

## Kết quả kiểm tra (PowerShell, chạy từ gốc repo, `PYTHONUTF8=1`)

| Lệnh | Kết quả | Log |
|---|---|---|
| `scripts/verify_lite.py` (smoke) | 9/9 PASS | [`evidence/smoke.txt`](evidence/smoke.txt) |
| `python -m pytest` | 24/24 PASS | [`evidence/pytest.txt`](evidence/pytest.txt) |
| `scripts/run_all.py` | 8/8 PASS | [`evidence/run_all.txt`](evidence/run_all.txt) |
| Bonus PoC | PASS | [`evidence/poc_bonus.txt`](evidence/poc_bonus.txt) |

Notebook nộp nằm trong [`notebooks/`](notebooks/). Chúng được thực thi từ đầu đến cuối bằng
`jupyter nbconvert --execute`, giữ nguyên output, 0 cell lỗi. Ảnh chụp kết quả chính nằm trong [`screenshots/`](screenshots/).

## Thay đổi so với đề bài

Chỉ **thêm** cell, không sửa logic hay hạ ngưỡng nào:

- Mỗi notebook có thêm cell Markdown **"Phân tích kết quả (học viên)"** giải thích số đo, cơ chế và giới hạn.
- **NB1:** thêm cell in nội dung `_delta_log/` và commit JSON. Thêm kiểm tra rằng write bị chặn không tạo version mới.
  Thay cờ hardcode `True` của tiêu chí schema enforcement bằng kiểm tra thật (`blocked and versions == [0]`).
- **NB4:** thêm cell assert chất lượng Gold mà notebook gốc chưa kiểm: đủ 3 tầng trên đĩa, ≥ 7 ngày × 3 model,
  p50 ≤ p95, cost > 0, error_rate ∈ [0, 1].

## Ghi chú môi trường

- `pip install` chạy rất chậm trên mạng của máy (PyPI ~100 KB/s, resolver backtrack lâu), nên đã chuyển sang `uv`.
  `make setup` cũng dùng `uv`.
- Số liệu thời gian (speedup NB2, thời gian MERGE/RESTORE) dao động giữa các lần chạy: NB2 đo được 10.3× ở lần chạy
  đầu và 25.8× ở lần được lưu. Các số deterministic (file count, pruning ratio, recall...) giống nhau giữa các lần chạy.
