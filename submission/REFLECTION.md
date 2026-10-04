# Reflection — Anti-pattern dễ vướng nhất

**Anti-pattern: ghi streaming thành small files rồi "để maintenance sau".**

Hệ thống tôi quan tâm là log LLM/agent: mỗi request ghi một sự kiện nhỏ, commit mỗi vài giây.
Tôi dễ vướng lỗi này vì ban đầu mọi thứ vẫn chạy ổn. Lab đã đo chi phí ẩn: NB2 cho thấy 200 file nhỏ làm point query chậm
16.6× so với sau OPTIMIZE + Z-ORDER. Ở NB5, metadata chiếm tới 293% dữ liệu. NB6 thì cho thấy VACUUM
không dọn file do job crash để lại, còn snapshot expiry của PyIceberg không xóa manifest list vật lý.
Với log tăng mỗi ngày, các vấn đề này cộng dồn thành hóa đơn S3 tính theo request và cold start chậm.

Cách phòng tránh:
1. Gom batch theo kích thước/thời gian khi ingest.
2. Lập lịch compaction + Z-order theo cột lọc nóng (tenant, model).
3. Chạy expiry kèm orphan sweep có age guard.
4. Theo dõi `numFiles` và kích thước file trung bình như một SLO, có cảnh báo.

**Sử dụng AI:** dùng Claude Code hỗ trợ setup, chạy notebook, soạn nháp giải thích và bonus;
chi tiết trong [AI_USAGE.md](AI_USAGE.md).
