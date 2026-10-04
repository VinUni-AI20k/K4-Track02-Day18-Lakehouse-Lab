# Khai Báo Sử Dụng AI (AI Usage Declaration)

Theo quy định tại [RULES.md](../docs/RULES.md) của bài lab K4-Track02-Day18:

### 1. Công cụ AI sử dụng
- **Công cụ:** Antigravity IDE (mô hình ngôn ngữ Gemini 3.8 Flash / Thinking).

### 2. Mục đích và phạm vi hỗ trợ
- **Đọc hiểu tài liệu và rubric:** Hỗ trợ tổng hợp các yêu cầu, tiêu chí chấm điểm từ `README.md`, `RUBRIC.md`, `CHECKPOINTS.md`, `RULES.md` và `SUBMISSION.md`.
- **Rà soát mã nguồn:** Phân tích logic của 8 notebook lightweight trong `notebooks/`, đối chiếu các assertion và cấu trúc dữ liệu theo đúng chuẩn format của Delta Lake và Apache Iceberg.
- **Xây dựng tài liệu Bonus Architecture:** Hỗ trợ cấu trúc tài liệu kiến trúc hệ thống LLM Observability quy mô 1B requests/ngày (`submission/bonus/ARCHITECTURE.md`), tính toán chi phí dung lượng lưu trữ (FinOps back-of-the-envelope math) và xây dựng PoC tokenization / lifecycle.
- **Tự động hóa build & xuất notebook:** Hỗ trợ viết script Python (`scripts/build_submission_notebooks.py`) để chuyển đổi các file `notebooks/*.py` sang định dạng `.ipynb`, thực thi và trích xuất outputs/screenshots cho bài nộp.

### 3. Cam kết tuân thủ quy chế
- Không dùng AI để làm sai lệch hoặc giả mạo số liệu/kết quả thực thi. Toàn bộ các notebook và bài test đều được chạy thực tế trên máy cục bộ với runtime Python 3.11.
- Toàn bộ assertions gốc trong mã nguồn được bảo toàn nguyên vẹn 100%, không hạ ngưỡng hay bỏ qua kiểm thử.
- Tự chạy và chịu trách nhiệm giải thích kết quả cùng các bằng chứng trong bài nộp.
