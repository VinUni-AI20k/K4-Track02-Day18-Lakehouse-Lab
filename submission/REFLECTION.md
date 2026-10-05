### Anti-Pattern: Small Files Problem

**Giải thích vấn đề:**
Trong các hệ thống phân tích nhật ký (log) hoặc LLM Observability như trace data, dữ liệu thường đến liên tục với tần suất cao nhưng kích thước mỗi sự kiện nhỏ. Nếu không quản lý tốt, điều này dẫn đến "Small Files Problem", tức là tạo ra hàng triệu file cực nhỏ. Điều này sẽ làm suy giảm hiệu suất nghiêm trọng khi truy vấn do chi phí I/O (mở file) lớn hơn nhiều so với việc đọc dữ liệu thực sự.

**Cách phòng tránh:**
1. **Compaction thường xuyên:** Sử dụng lịch trình chạy lệnh `OPTIMIZE` hoặc compaction (như NB6) định kỳ để gộp các file nhỏ thành file lớn (~1GB).
2. **Data Skipping/Pruning:** Kết hợp `Z-ORDER` theo các cột hay truy vấn để tối ưu hóa vị trí dữ liệu trong không gian lưu trữ, giúp bỏ qua các file không cần thiết nhanh chóng.

**AI Usage:** Đã sử dụng Antigravity AI assistant để tự động cấu hình môi trường, chạy tests, và hỗ trợ soạn thảo file nộp.
