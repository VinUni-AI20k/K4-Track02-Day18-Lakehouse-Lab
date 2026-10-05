# Reflection — Anti-pattern: small files từ streaming ingestion

Hệ thống tôi quan tâm là log quan sát LLM ghi liên tục theo micro-batch vài giây một lần. Đây là kịch bản dễ vướng **small-file problem** nhất: mỗi commit đều đúng, nhưng sự tích tụ mới là lỗi.

Lab cho thấy điều này bằng số đo. Ở NB6, 200 commit sinh 200 file trung bình 51,5 KB. Compaction giảm xuống
11 file (18×), Z-order giúp truy vấn theo `user_id` chỉ mở 1/10 file. Ở NB5, metadata còn lớn hơn data (286%).
Small files làm chậm cả đọc dữ liệu lẫn lập kế hoạch truy vấn, và phí GET tăng theo số file.

Cách phòng tránh tôi sẽ áp dụng:
1. Tăng trigger interval hoặc gom batch trước khi commit.
2. Lên lịch compaction + clustering theo cột hay được lọc (tenant, model).
3. Luôn chạy expiry *kèm* orphan sweep, vì NB6 cho thấy expiry một mình không xoá file vật lý.
4. Tạo checkpoint log định kỳ.
5. Theo dõi chỉ số "số file / partition" và "kích thước file trung bình" như một SLO.

*AI:* có dùng Claude Code hỗ trợ — xem [AI_USAGE.md](AI_USAGE.md).
