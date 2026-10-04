# Thông tin bài nộp

| Mục | Giá trị |
|---|---|
| Họ tên | Nguyễn Vũ Huy |
| MSSV | 2A202602662 |
| Mã bài | K4-Track02-Day18 — Lakehouse Lab |
| Repo | `vuhuyng04/K4-Track02-Day18-NguyenVuHuy-2A202602662-Lakehouse-Lab` |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Python | 3.13.13 (64-bit, venv `.venv`) — trong khoảng hỗ trợ 3.10–3.14; máy không có 3.11 |
| Hệ điều hành | Windows 11 Home (10.0.26200), PowerShell + Git Bash |
| Thư viện chính | deltalake 1.6.6 · pyiceberg 0.12.0 · duckdb 1.5.6 · polars 1.44.2 · pyarrow 25.0.1 · numpy 2.5.3 · jupyterlab 4.6.4 · nbconvert 7.17.1 |

## Kết quả kiểm tra (lệnh PowerShell tương đương `make`, `$env:PYTHONUTF8='1'`)

| Lệnh | Kết quả |
|---|---|
| `python scripts/verify_lite.py` (smoke) | **9/9 PASS** |
| `python scripts/generate_data_lite.py` | 200 000 dòng Bronze, 9 948 bản trùng gieo sẵn, 7 ngày UTC từ 2026-04-01 |
| `python scripts/generate_ai_data.py` | 2 000 docs dim=256 · 200 blob (12.5 MB) · 1 578 step / 300 session |
| `python -m pytest` | **24 passed** |
| `python scripts/run_all.py` | **8/8 PASS** (35.5 s) |

## Cách tạo notebook nộp

1. `jupytext --to notebook notebooks/0[1-8]_*.py`
2. `jupyter nbconvert --to notebook --execute --inplace` từng notebook (tuần tự) → output được lưu trong `.ipynb`.
3. Chép sang `submission/notebooks/`. Mỗi notebook có thêm một Markdown cell **"Giải thích kết quả"** ở cuối.
4. Hai cell code do học viên thêm (không sửa mã/ngưỡng gốc):
   - NB1: in danh sách `_delta_log/*.json` và nội dung commit v0, v1 (bằng chứng transaction log).
   - NB4: kiểm tra đủ hợp đồng Gold mà notebook gốc chưa assert (≥ 7 ngày mỗi model, p50 ≤ p95, cost > 0, error_rate ∈ [0, 1]).

Screenshots trong `submission/screenshots/` được chụp từ bản HTML (`nbconvert --to html`) của chính các notebook đã nộp,
đặt tên `nbXX_<kết quả>.png` (42 ảnh, ≥ 3 ảnh/notebook).

## Bonus

Có — chủ đề **A. LLM observability 1B requests/ngày**: [`bonus/ARCHITECTURE.md`](bonus/ARCHITECTURE.md), PoC tại [`bonus/poc/`](bonus/poc/).
