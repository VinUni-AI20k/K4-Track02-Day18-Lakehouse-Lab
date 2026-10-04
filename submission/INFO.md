# Thông tin người nộp

| Trường | Giá trị |
|---|---|
| Họ và tên | Dương Hà Đức Anh |
| MSSV | 2A202602977 |
| Mã bài | K4-Track02-Day18 |
| Đường chạy | **Lightweight** (`deltalake` 1.x + `pyiceberg` + DuckDB + Polars) cho cả 8 notebook |
| Python | 3.14.3 (khoảng cấu hình 3.10–3.14) |
| Hệ điều hành | Windows 11 Pro (10.0.26200) |
| Repo | `K4-Track02-Day18-DuongHaDucAnh-2A202602977-Lakehouse-Lab` |

## Phiên bản thư viện đã dùng

| Gói | Phiên bản |
|---|---|
| deltalake | 1.6.6 |
| pyiceberg | 0.12.0 |
| duckdb | 1.5.6 |
| polars | 1.44.2 |
| pyarrow | 25.0.1 |
| numpy | 2.5.3 |

## Kết quả kiểm tra

| Lệnh | Kết quả |
|---|---|
| `scripts/verify_lite.py` (smoke) | **9/9 PASS** |
| `pytest` | **24/24 PASS** (2.7 s) |
| `scripts/run_all.py` (8 notebook headless) | **8/8 PASS** (28.4 s) |
| Thực thi 8 `.ipynb` bằng nbconvert (giữ output) | **8/8 PASS**, không có cell lỗi |

NB1–NB4 dùng đường lightweight (`deltalake`), không dùng Spark. Toàn bộ kết quả
trong `submission/notebooks/` được sinh trên máy cá nhân với cấu hình ở trên.

## Cấu trúc bài nộp

```
submission/
├── INFO.md                      # file này
├── REFLECTION.md                # reflection ≤ 200 từ
├── AI_USAGE.md                  # khai báo phạm vi dùng AI
├── notebooks/                   # 8 .ipynb đã chạy, giữ output
├── screenshots/                 # 9 ảnh, phủ NB1–NB8
├── _make_screenshots.py         # script render ảnh (không thuộc runtime lab)
└── bonus/
    ├── ARCHITECTURE.md          # architecture brief (bonus)
    └── poc/
        └── poc_tokenize_pin.py  # spike: token hóa PII + ghim version + prune
```

## Cách tái lập

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/verify_lite.py
.\.venv\Scripts\python.exe scripts/generate_data_lite.py
.\.venv\Scripts\python.exe scripts/generate_ai_data.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/run_all.py
```
