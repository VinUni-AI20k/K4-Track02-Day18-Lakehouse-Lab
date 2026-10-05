# Reflection

**Anti-pattern: vector index bị dùng như system-of-record.**

NB7 cho thấy rõ. Sau một yêu cầu xoá dữ liệu, bảng Delta còn 1.992 dòng và trả 0
kết quả, nhưng external index vẫn giữ 2.000 vector và trả đủ 8 tài liệu lẽ ra đã bị
xoá, rồi đưa thẳng chúng vào prompt RAG.

Trợ lý hỏi đáp nội bộ trên tài liệu công ty mà tôi quan tâm rất dễ mắc lỗi này.
Embedding chỉ sinh một lần lúc ingest; mọi truy vấn sau đó đi thẳng vào vector DB.
Bảng gốc thành kho bị bỏ quên, nên xoá ở tầng bảng không lan tới index; pipeline
đồng bộ một chiều kiểu upsert thường quên hẳn delete, nên sai lệch tồn tại vĩnh
viễn chứ không tự lành.

Cách phòng tránh: xem index là dữ liệu dẫn xuất, luôn rebuild được từ bảng gốc; bật
Change Data Feed để đẩy delete thành sự kiện; ghi table version vào index; cảnh báo
khi số tài liệu còn trong index nhưng đã mất khỏi bảng khác 0.

AI: xem AI_USAGE.md
