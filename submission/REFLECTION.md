# Reflection — Anti-pattern: "xoá ở bảng là xong"

Anti-pattern tôi chọn: coi `DELETE` ở version hiện tại là đã xoá dữ liệu. Lab cho thấy điều ngược lại. Ở NB8, `user_007` về 0 dòng nhưng v0 vẫn time-travel được. Ở NB7, bảng có 0 hit nhưng external vector index vẫn trả 8 tài liệu đã xoá. Ở NB6, PyIceberg expire 17 snapshot mà xoá **0** file vật lý.

Hệ thống tôi quan tâm là chatbot RAG tiếng Việt trên dữ liệu khách hàng, nơi yêu cầu xoá theo Nghị định 13/2023 là bình thường. Dữ liệu ở đây bị nhân bản rất nhiều: Bronze, Silver, snapshot training đã pin version, vector index, cache. Một lệnh xoá chỉ chạm vào một bản sao.

Cách phòng tránh:
1. Coi xoá là một **quy trình**: DELETE → phát sự kiện CDF cho index/cache → VACUUM / expire + orphan sweep sau retention → kiểm tra bằng cách liệt kê file thật trên storage.
2. Đặt retention có chủ đích, ngắn hơn hạn trả lời yêu cầu xoá.
3. Ghi provenance và `subject_id` từ lúc ingest để tìm được mọi bản sao.
4. Dùng crypto-shredding cho snapshot bất biến.

*Dùng AI:* xem [AI_USAGE.md](AI_USAGE.md).
