# Reflection

Anti-pattern dễ xuất hiện nhất trong hệ thống dữ liệu tôi quan tâm là **quá nhiều file nhỏ**. Khi pipeline ghi liên tục theo từng batch ngắn, số lượng object tăng nhanh dù tổng dung lượng chưa lớn. Kết quả NB2 và NB6 cho thấy hậu quả không chỉ là scan chậm: metadata phình to, số request tăng và chi phí maintenance cũng cao hơn.

Mình sẽ phòng tránh bằng cách đặt kích thước file mục tiêu ngay từ thiết kế writer, theo dõi số file và dung lượng trung bình theo partition, rồi chạy compaction theo ngưỡng thay vì theo lịch cố định. Với cột lọc phổ biến, clustering hoặc Z-order chỉ nên thực hiện sau khi đo pruning thực tế. Snapshot expiry, orphan cleanup và checkpoint cần được vận hành như các job riêng có metric trước/sau, vì một thao tác không thể thay thế toàn bộ quy trình bảo trì.

Phạm vi sử dụng AI được khai báo tại [AI_USAGE.md](AI_USAGE.md).
