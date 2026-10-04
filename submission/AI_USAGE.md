# Khai báo sử dụng AI

Công cụ: OpenAI Codex trong ứng dụng desktop.

Codex đọc README và toàn bộ hướng dẫn phần bắt buộc trong docs, đọc mã tám
notebook lightweight cùng helper/test liên quan; cài dependencies; chạy smoke,
pytest, dữ liệu mẫu và notebook trong môi trường làm việc của người nộp.
AI sửa kiểm tra NB1/NB3/NB4, thêm script lưu notebook/evidence, soạn giải thích
kết quả và bản nháp reflection, chuẩn bị screenshots từ output thực tế.

Số liệu được sinh bằng mã đề bài và thu từ lần thực thi thật. Không gọi LLM để
sinh embeddings: corpus, vectors và agent traces đều là fixture tổng hợp của lab.
Không sửa ngưỡng rubric hoặc bỏ assertion. Không thực hiện phần bonus.

Giải thích và reflection do AI hỗ trợ soạn. Người nộp cần đọc, hiểu, chỉnh nếu
không phù hợp với trải nghiệm của mình và chịu trách nhiệm khi trình bày kết quả.
Không khẳng định người nộp đã tự chạy từng cell hay tự viết các đoạn do AI soạn.

Nguồn mã và khái niệm chính: repository đề bài
https://github.com/VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab và các tài liệu
README, docs/CHECKPOINTS.md, docs/RUBRIC.md. Các giới hạn NB8 được giữ theo đề bài;
không suy diễn mô phỏng thành MCP production hay chứng nhận quyền sử dụng dữ liệu.
