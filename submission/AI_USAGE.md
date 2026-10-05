# Khai báo sử dụng AI

Công cụ: **Claude Code** (model Claude Sonnet 5.5) chạy trong VS Code.

## AI đã làm

* Phân tích cấu trúc repo và tài liệu chấm điểm (README, RUBRIC, CHECKPOINTS, SUBMISSION, RULES).
* Dựng venv Python 3.11 và cài `requirements.txt`. Lần cài đầu lỗi `SSL: CERTIFICATE_VERIFY_FAILED`;
  đã xử lý bằng `pip --use-feature=truststore` (dùng kho chứng chỉ của Windows), **không** tắt xác thực TLS.
  Cài thêm `pillow` vào venv chỉ để dựng ảnh bằng chứng (không nằm trong `requirements.txt`).
* Chạy smoke test, sinh dữ liệu, `pytest`, `run_all.py`; chuyển 8 notebook sang `.ipynb` bằng jupytext và thực thi
  bằng `nbconvert --execute` để giữ output thật.
* Kiểm chứng các điểm mà rubric nói notebook chưa chứng minh: thêm cell bằng chứng cho NB1 (đọc `_delta_log/`,
  bắt đúng lỗi `Cannot cast string 'thirty' to value of Int64 type`, số dòng không đổi) và NB4 (Gold có
  8 ngày × 3 model, p50 ≤ p95, cost > 0, error_rate ∈ [0, 1]).
* Viết cell Markdown "Phân tích kết quả" cho từng notebook, soạn nháp `REFLECTION.md` và `INFO.md`.

## Bonus (`bonus/`)

* AI chọn Topic A, soạn `ARCHITECTURE.md` và viết/chạy PoC. Số liệu hiệu năng (12,3 MB/s/core, 0 PII lọt trên corpus tổng hợp,
  TTL xoá byte thật, 200 hit từ index cũ) là **kết quả thật của lần chạy PoC**; PoC dùng corpus tổng hợp do chính PoC sinh ra.
* Đơn giá AWS và các số về Kinesis/Flink/Athena là **giả định từ bảng giá niêm yết AWS mà AI nhớ, chưa tra lại trực tuyến**;
  tài liệu ghi rõ điều này. Người nộp cần kiểm tra giá trước khi bảo vệ trong design review.
* Trong lúc rà soát, AI đã sửa một lập luận sai của chính mình (kích thước partition ở phương án `hour + bucket`) và dùng số đo
  thật của PoC để thay giả định 30 MB/s ban đầu cho redactor.

## Về ảnh trong `screenshots/`

Đây **không phải ảnh chụp cửa sổ Jupyter**. Chúng là ảnh dựng từ chính text output đã lưu trong các `.ipynb`
đã thực thi (một ký tự `⚠️` được hiển thị thành `⚠`; riêng `nb02_optimize.png` rút gọn danh sách min/max file,
phần đầy đủ có trong notebook). Không có số liệu nào được viết tay. Nếu giảng viên yêu cầu ảnh chụp màn hình thật,
hãy mở các notebook trong `submission/notebooks/` và chụp lại.

## AI không làm

* Không sửa mã nguồn `notebooks/*.py`, không hạ ngưỡng, không bỏ assertion.
* Không bịa số liệu: mọi con số trong phần phân tích lấy từ lần thực thi cuối. Các số đo theo thời gian
  (NB2 speedup, NB7 độ trễ) dao động giữa các lần chạy; bản nộp ghi giá trị của lần chạy cuối và nêu rõ độ dao động.

## Trách nhiệm của người nộp

Phần phân tích và reflection là bản nháp do AI soạn từ output thật; người nộp cần đọc, hiểu, chỉnh lại theo
cách hiểu của mình (đặc biệt `REFLECTION.md` — chọn hệ thống/dữ liệu mình thực sự quan tâm) trước khi nộp.
