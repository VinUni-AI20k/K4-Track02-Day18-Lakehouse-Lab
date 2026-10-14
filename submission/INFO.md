# Thông tin bài nộp

| | |
|---|---|
| **Họ tên** | Đỗ Quang Vinh |
| **MSSV** | 2A202602989 |
| **Mã bài** | K4-Track02-Day18 — Lakehouse Lab |
| **Repo (fork)** | https://github.com/quangvinh12a1/K4-Track02-Day18-DoQuangVinh-2A202602989-Lakehouse-Lab |
| **Đường chạy** | Lightweight cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| **Python** | 3.12 (64-bit), `.venv` tạo bằng `py -3.12 -m venv .venv` |
| **Hệ điều hành** | Windows 11 Home (10.0.26200), PowerShell / Git Bash, `PYTHONUTF8=1` |
| **Thư viện chính** | deltalake 1.6.6, pyiceberg 0.12.0, duckdb 1.5.6, polars 1.44.2, pyarrow 25.0.1, numpy 2.5.4, jupyterlab 4.6.4 |

## Kết quả kiểm tra

| Lệnh | Kết quả |
|---|---|
| `scripts/verify_lite.py` (smoke) | 9/9 ✓ |
| `python -m pytest` | **24 passed** |
| `scripts/run_all.py` | **8/8 notebook PASS** |

## Bài nộp

- `notebooks/`: 8 notebook đã thực thi bằng Jupyter kernel của `.venv` (giữ output). Cuối mỗi notebook có cell **"Kết quả & giải thích"** với số đo và câu trả lời cho các câu hỏi của bước đó.
- `screenshots/`: mỗi notebook một ảnh các cell kết quả chính (`nb01_delta_log.png` … `nb08_agents.png`).
- `REFLECTION.md`: anti-pattern lakehouse; `AI_USAGE.md`: khai báo dùng AI.
- `bonus/ARCHITECTURE.md` + `bonus/poc/`: bonus Topic A.

## Thay đổi mã nguồn notebook (để có bằng chứng thật)

- **NB1** (`notebooks/01_delta_basics.py`): cờ "schema enforcement blocked bad write" không còn hardcode `True`. Giờ cờ lấy từ chính cell ghi sai kiểu (có exception **và** version bảng không đổi). Thêm cell in nội dung các commit JSON trong `_delta_log/`.
- **NB4** (`notebooks/04_medallion.py`):
  1. Thêm `SET TimeZone = 'UTC'`. Trên máy ở múi giờ Asia/Saigon, `CAST(ts AS DATE)` chia 7 ngày UTC thành 8 ngày cục bộ, trong đó hai ngày đầu và cuối bị thiếu giờ (Gold 24 dòng → giờ là 21 = 7 × 3).
  2. Thêm cell kiểm tra đầy đủ hợp đồng Gold: p50 ≤ p95, cost > 0, error_rate ∈ [0, 1], đủ lưới ngày × model, 3 bảng trên storage.

Không sửa `tests/`, `scripts/` hay dữ liệu sinh.
