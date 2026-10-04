# K4-Track02-Day18 — Lakehouse Lab

| Mục | Giá trị |
|---|---|
| Họ tên | Phạm Long Nhật (Pham Long Nhat) |
| MSSV | 2A202602844 |
| Mã bài | K4-Track02-Day18 |
| Repo | https://github.com/Nhatcony0902/K4-Track02-Day18-PhamLongNhat-2A202602844-Lakehouse-Lab |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Hệ điều hành | Windows 11 Pro 10.0.26200 |
| Python | 3.11.9 (venv `.venv`, cài bằng `uv pip install -r requirements.txt`) |
| Thư viện | deltalake 1.6.6 · pyiceberg 0.12.0 · duckdb 1.5.6 · polars 1.44.2 · pyarrow 25.0.1 · numpy 2.4.6 |

## Kết quả kiểm tra (PowerShell, từ thư mục gốc repo)

| Lệnh | Kết quả |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_lite.py` | 9/9 checks PASS |
| `.\.venv\Scripts\python.exe -m pytest` | 24 passed |
| `.\.venv\Scripts\python.exe scripts/run_all.py` | 8/8 notebooks PASS |

Notebook nộp nằm ở `submission/notebooks/` — thực thi bằng
`jupyter nbconvert --to notebook --execute` (kernel Python 3.11 của venv), giữ nguyên output.
Cuối mỗi notebook có cell **"📝 Phân tích kết quả"** (giải thích số liệu) và cell **"❓ Trả lời câu hỏi"** (trả lời các câu hỏi "Giải thích" ở mục 3.1–3.8 của hướng dẫn lab).
Screenshots ở `submission/screenshots/` được render từ chính output đã lưu trong các notebook này.

## Thay đổi so với đề bài (không hạ ngưỡng nào)

- **NB1:** check "schema enforcement blocked bad write" trước đây hardcode `True`; nay dùng cờ thật
  `bad_write_blocked` và thêm check lần ghi lỗi không tạo commit.
- **NB4:** thêm cell assert chất lượng Gold (3 tầng trên đĩa, ≥ 7 ngày cho mỗi model × 3 model,
  p50 ≤ p95, `cost_usd > 0`, `error_rate ∈ [0,1]`, không null) và in số dòng/ngày + TimeZone.
- **NB6:** sửa phần *in* số liệu — `count_files()` đếm cả checkpoint tự động (v99, v199) trong `_delta_log/`
  thành "orphan"; dry-run VACUUM in `0 B` do dùng đường dẫn tương đối; Job 5 in tên checkpoint cũ (v99) thay vì
  checkpoint vừa tạo (v203). Siết thêm 2 check: disk = log sau khi dọn orphan, checkpoint trùng version hiện tại.
- Thêm Markdown "Phân tích kết quả" vào cuối 8 notebook.
