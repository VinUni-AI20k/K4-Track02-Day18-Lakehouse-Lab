# Reflection

Anti-pattern tôi quan tâm nhất là **small files**. Trong hệ thống thu thập log và theo dõi yêu cầu LLM, dữ liệu thường được ghi liên tục theo các micro-batch nhỏ. Nếu mỗi batch tạo một file, số file sẽ tăng nhanh dù tổng dung lượng chưa lớn. Điều này làm tăng chi phí liệt kê object, đọc metadata và lập kế hoạch; truy vấn phải mở nhiều file nên chậm và lãng phí tài nguyên.

Để phòng tránh, tôi sẽ kiểm soát kích thước batch và tần suất ghi từ ingestion, đặt kích thước file mục tiêu và chạy compaction định kỳ. Các cột thường dùng để lọc sẽ được clustering hoặc Z-order để tăng file skipping. Tôi cũng sẽ theo dõi số file, kích thước file trung bình, thời gian lập kế hoạch và chi phí object request. Retention và vacuum chỉ được áp dụng sau khi xem xét reader đang hoạt động và yêu cầu time travel.

Tôi đã sử dụng AI để đọc yêu cầu, giải thích khái niệm và hỗ trợ xử lý lỗi. Toàn bộ notebook, số liệu và output trong bài nộp đều do tôi tự chạy và kiểm tra.
