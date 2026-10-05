# Khai báo sử dụng AI

**Công cụ:** Claude Code (model Claude Opus 5.5) chạy trong VS Code, trên máy cá nhân của người nộp.

## AI đã hỗ trợ

- Đọc README, CHECKPOINTS, RUBRIC, RULES, SUBMISSION và 8 notebook để lập thứ tự làm từ CP0 đến CP9.
- Dựng môi trường: tạo `.venv` Python 3.11 bằng `uv`, cài `requirements.txt`, đăng ký Jupyter kernel cho venv.
  Kernel `python3` mặc định trên máy trỏ về Anaconda nên ban đầu báo thiếu `polars`.
- Chạy smoke test, sinh dữ liệu, pytest, `run_all.py` và thực thi 8 notebook bằng `nbconvert --execute`.
  Mọi số liệu đều lấy từ các lần chạy thật trên máy này.
- Phát hiện và sửa các chỗ đo sai hoặc thiếu bằng chứng trong NB1, NB3, NB4, NB6, NB8 (xem bảng
  "Thay đổi so với mã đề bài" trong [INFO.md](INFO.md)). Ví dụ: lỗi múi giờ ở Gold NB4, checkpoint tự động bị đếm nhầm ở NB6.
- Soạn nháp các ô "🔎 Giải thích kết quả" trong notebook, cùng `INFO.md` và `REFLECTION.md`.
- Viết script render screenshot từ output đã lưu (nbconvert HTML + Edge headless).

## Nguyên tắc đã giữ

- Không tạo output giả. Không hạ ngưỡng, không xóa hay nới lỏng assertion. Các thay đổi chỉ làm phép kiểm tra chặt hơn
  hoặc sửa phép đo sai, và đều kèm lý do.
- Không đưa API key, secret hay dữ liệu thật vào repo hoặc prompt. Lab chỉ dùng dữ liệu giả.

## Trách nhiệm của người nộp

Người nộp rà soát lại mã đã sửa, các số liệu và phần giải thích, và phải tự giải thích được cơ chế đằng sau
mỗi kết quả (transaction log, file skipping, time travel, hidden partitioning, maintenance, vòng đời embedding, provenance).
