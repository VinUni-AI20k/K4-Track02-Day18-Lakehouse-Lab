# Reflection

**Anti-pattern: small-file problem do ingestion streaming không kèm compaction.**

Với hệ LLM observability tôi quan tâm — 1B request/ngày, ~5 KB/request, ~5 TB/ngày —
ingestion gần như liên tục sẽ ghi ra vô số file nhỏ (một file mỗi micro-batch). Delta
không tự gộp: mỗi commit thêm file, metadata `_delta_log/` phình ra, và mỗi query phải
mở hàng nghìn file chỉ để đọc vài giây dữ liệu. Đây chính là điều NB2 và NB6 mô phỏng:
200 file nhỏ làm query chậm, sau `OPTIMIZE` còn 55 file và nhanh ~9,8×.

Hệ của tôi dễ gặp vì dữ liệu đến theo dòng thời gian thật, không theo batch lớn; áp lực
giữ dashboard cost/latency refresh mỗi 5 phút lại càng khuyến khích flush sớm.

**Phòng tránh:** đặt lịch `OPTIMIZE`/`Z-ORDER` theo partition ngày, chọn kích thước file
mục tiêu ~128–256 MB, dùng checkpoint định kỳ (NB6 Job 5), và theo dõi số file/partition
như một SLO — không chờ query chậm mới xử lý.

**Phạm vi sử dụng AI:** xem [`AI_USAGE.md`](AI_USAGE.md).
