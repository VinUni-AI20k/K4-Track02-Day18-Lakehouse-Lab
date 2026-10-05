# Thông tin bài nộp

| Mục | Giá trị |
|---|---|
| Họ tên | Nguyen Tien Luong |
| MSSV | 2A202602378 |
| Mã bài | K4-Track02-Day18 |
| Repo | `K4-Track02-Day18-NguyenTienLuong-2A202602378-Lakehouse-Lab` |
| Đường chạy | **Lightweight** cho cả 8 notebook (NB1–NB4 **không** dùng Spark) |
| Python | 3.11.9 |
| Hệ điều hành | Windows 11 Home (10.0.26200), PowerShell |

## Phiên bản thư viện đã dùng

`deltalake 1.6.6` · `pyiceberg 0.12.0` (`pyiceberg-core 0.10.1`) · `duckdb 1.5.6` · `polars 1.44.2` ·
`pyarrow 25.0.1` · `numpy 2.4.6` · `jupyterlab 4.6.4` · `jupytext 1.19.6` · `pytest 9.1.1`

NB6 mô tả hành vi của `VACUUM` (deltalake) và `expire_snapshots` (PyIceberg) **theo đúng các phiên bản trên**.

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| `scripts/verify_lite.py` (smoke) | 9/9 PASS |
| `pytest` | 24/24 PASS |
| `scripts/run_all.py` | 8/8 PASS (~26 s) |
| 8 notebook `.ipynb` thực thi bằng `jupyter nbconvert --execute` | 8/8 không lỗi |

## Nội dung thư mục

* `notebooks/` — 8 notebook đã thực thi, giữ output. NB1 và NB4 có thêm 1 cell bằng chứng; mỗi notebook có
  1 cell Markdown "Phân tích kết quả" ở cuối (các cell này được đánh dấu `submitter_added` trong metadata).
  Mã nguồn gốc của lab (`notebooks/*.py`) **không bị sửa**, không hạ ngưỡng hay bỏ assertion.
* `screenshots/` — ảnh bằng chứng cho từng notebook; xem ghi chú về cách tạo ảnh trong [AI_USAGE.md](AI_USAGE.md).
* `bonus/ARCHITECTURE.md` — bonus cá nhân, Topic A (LLM observability 1B req/ngày); `bonus/poc/retention_and_redaction_poc.py` — PoC chạy được
  (redactor PII + TTL 7 ngày trên Iceberg), xem §7 của tài liệu để biết kết quả và giới hạn.
* `REFLECTION.md`, `AI_USAGE.md`.
