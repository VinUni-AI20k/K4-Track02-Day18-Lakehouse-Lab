# Reflection

Anti-pattern tôi quan tâm nhất là tách embedding sang một vector index nhưng chỉ đồng bộ theo kiểu upsert. Với hệ thống RAG, cách này dễ xảy ra vì index phục vụ truy vấn nhanh còn lakehouse giữ dữ liệu gốc. Khi một tài liệu bị xóa, hết hạn hoặc thay đổi quyền sử dụng, index cũ vẫn có thể trả nội dung đó; NB7 tái hiện đúng lỗi này với 0 hit trong bảng nhưng còn 8 hit ở index.

Tôi sẽ coi lakehouse là system-of-record và vector index chỉ là artifact có thể tái tạo. Mọi thay đổi phải có khóa ổn định và version; consumer đọc Change Data Feed, xử lý cả insert, update và delete theo cách idempotent. Pipeline cần theo dõi lag, đối chiếu định kỳ ID giữa bảng và index, chặn phục vụ khi vượt SLA, đồng thời pin table version cho mỗi lần build để rollback được. Retention/vacuum chỉ chạy sau khi
mọi consumer đã qua watermark an toàn. Cách này nối lifecycle của dữ liệu, embedding và index thay vì dựa vào một batch sync dễ quên delete.

Phạm vi sử dụng AI được ghi tại [AI_USAGE.md](AI_USAGE.md).
