# AI Usage Declaration

Trong bài lab K4-Track02-Day18 (Lakehouse Engineering), công cụ AI Assistant (Antigravity IDE - Google DeepMind) được sử dụng với các phạm vi sau:

1. **Hỗ trợ tự động hóa môi trường & thực thi:**
   - Chuyển đổi các file kịch bản notebook giữa định dạng Python percent (`.py`) và Jupyter Notebook (`.ipynb`) thông qua `jupytext`.
   - Thực thi headless toàn bộ 8 notebook bằng `nbconvert` với kernel Python của `.venv` để đảm bảo kết quả trung thực, tự động thu thập output và lưu vết vào file `.ipynb`.
   - Sinh ảnh chụp kết quả kiểm tra (card screenshots) từ log terminal thực tế lưu vào `submission/screenshots/`.

2. **Phân tích kỹ thuật & Trả lời câu hỏi trọng tâm:**
   - Phân tích cơ chế kỹ thuật sâu: Schema Enforcement vs Schema Evolution, Transaction Log ACID guarantees, Hidden Partitioning trong Apache Iceberg, File skipping qua Z-order statistics, và vòng đời vector embeddings với Change Data Feed (CDF).
   - Kiểm tra đối chiếu số liệu benchmark thực tế đo được trên máy so với các ngưỡng yêu cầu của [RUBRIC.md](../docs/RUBRIC.md).
