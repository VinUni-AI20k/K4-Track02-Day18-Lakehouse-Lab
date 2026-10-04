# Khai báo sử dụng AI

Công cụ: Codex trong phiên làm việc ngày 04/10/2026 (UTC+7).

AI đọc toàn bộ các file nguồn/tài liệu trong repo; giải thích rubric; tạo venv và cài dependencies; chỉnh NB1 để kiểm tra schema enforcement thực tế và NB4 để assert đủ chất lượng Gold; thêm script thực thi Jupyter, lưu output, logs, metrics và export ảnh. AI soạn bản giải thích notebook, reflection và architecture brief; tra cứu tài liệu Delta/Iceberg chính thức để dẫn nguồn bonus.

Số liệu phần bắt buộc được lấy từ lần chạy thực trên máy qua Python/Jupyter, không tạo thủ công. Ảnh là screenshot của HTML render từ output notebook thật; HTML đầy đủ và logs giữ trong evidence/logs. Các chi phí bonus là giả định thiết kế có ghi nhãn, không phải benchmark hoặc hóa đơn production. Không hạ ngưỡng, bỏ assertion hay giả rằng Spark/production PoC đã được chạy.

Đây là bộ bài chuẩn bị với hỗ trợ AI. Theo docs/RULES.md, người nộp chịu trách nhiệm tự chạy, kiểm tra, hiểu và giải thích kết quả. Trước khi nộp, người nộp cần thực hiện hướng dẫn chạy lại trong HUONG_DAN_NOP_BAI.md và sửa reflection nếu nội dung chưa phản ánh hiểu biết của mình. Không khẳng định người nộp đã làm bước này khi chưa thực hiện.

Các sửa đổi so với đề:

- NB1: thay flag True cố định bằng exception flag, kiểm tra failed write không tạo version/đổi row count, in transaction log JSON.
- NB4: đặt timezone DuckDB UTC để date buckets khớp generator và không phụ thuộc timezone Windows; in đủ Gold rows; assert số model/ngày, đủ lưới date-model, p50<=p95, chi phí dương và error_rate hợp lệ.
- Script nộp: thêm bootstrap để notebook nằm trong submission vẫn tìm được helper ở repo; chạy kernel riêng cho từng notebook, không giả output bằng chuyển `.py` sang `.ipynb`.
- Không sửa tests của đề; không chạy nhánh Spark/macOS hoặc harness Unix `simulate_students.py` trên Windows này vì đó là các đường tùy chọn, không checkpoint bắt buộc.
