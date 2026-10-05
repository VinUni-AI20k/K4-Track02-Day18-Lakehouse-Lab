# Reflection — Small files & bỏ quên maintenance

Hệ thống tôi quan tâm là log của ứng dụng LLM: mỗi request sinh một bản ghi prompt/response,
token, latency, cost. Anti-pattern tôi dễ vướng nhất là **small files do streaming ingestion mà
không có job maintenance**. Dashboard cần dữ liệu mới vài phút, nên phản xạ tự nhiên là commit
thật thường xuyên.

Lab cho tôi thấy cái giá cụ thể. NB2: 200 file nhỏ khiến point query phải mở cả 200 file. Sau
compaction và Z-order chỉ còn 1/55 file cần đọc, nhanh hơn 13.4×. NB6: compaction giảm 18× số
file. Nhưng VACUUM của delta-rs không thấy 3 file orphan chưa commit, còn expire snapshot của
PyIceberg không xóa file vật lý (avro 40 → 40). "Có chạy maintenance" chưa có nghĩa là bill
storage giảm.

Cách phòng tránh: chọn commit interval theo SLA thật (60 s thay vì 5 s); lên lịch đủ các job
compaction, clustering theo tenant, expire và orphan sweep thành cặp; alert khi kích thước file
trung bình < 64 MB. Quan trọng nhất là đo byte trên đĩa sau mỗi job, không chỉ tin số dòng.

*Sử dụng AI:* có — xem [AI_USAGE.md](AI_USAGE.md).
