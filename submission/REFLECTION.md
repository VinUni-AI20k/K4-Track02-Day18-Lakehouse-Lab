# Reflection — Anti-pattern: "Vector DB là system-of-record"

Hệ thống tôi quan tâm là RAG nội bộ trên tài liệu có dữ liệu cá nhân. Anti-pattern dễ vướng
nhất là coi **vector DB bên ngoài là nơi lưu chính** cho embeddings, còn lakehouse chỉ là
nguồn nạp một chiều.

NB7 cho thấy hậu quả bằng số: sau yêu cầu xoá của `user_042`, bảng Delta còn **0 hit**
nhưng external index vẫn trả **8 hit**. Pipeline sync thường chỉ upsert, nên delete bị quên —
dữ liệu đã xoá tiếp tục chui vào prompt cho đến lần rebuild, hoặc mãi mãi. NB8 nhắc thêm:
xoá ở version hiện tại chưa xoá file cũ do time travel giữ lại.

Cách phòng tránh:

1. Lakehouse là system-of-record; vector index chỉ là **derived index có thể rebuild**.
2. Index subscribe **Change Data Feed**, xử lý cả sự kiện `delete` (NB7 có 8 delete event mang `doc_id`).
3. Khi quy mô cho phép, giữ vector ngay trong bảng (int8 nhỏ 5.8×, recall@10 0.904) để vòng đời do bảng thực thi.
4. Erasure phải kèm retention + VACUUM và quét các bản sao phái sinh.

Phạm vi dùng AI: xem [AI_USAGE.md](AI_USAGE.md).
