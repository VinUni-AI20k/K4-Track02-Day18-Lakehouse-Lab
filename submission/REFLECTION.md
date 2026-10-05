# Reflection

Anti-pattern tôi chọn là bỏ qua maintenance sau khi ingestion đã chạy được.
Với hệ thống LLM observability, log đến liên tục; mỗi micro-batch nhỏ tạo thêm
file, làm dashboard phải mở nhiều file và đọc thêm metadata. Tăng compute chỉ
che triệu chứng, còn chi phí storage tiếp tục tăng vì file cũ chưa được thu hồi.

NB6 giúp phân biệt compaction, vacuum và orphan removal. Compaction giảm số
file đang dùng nhưng tạm tăng bytes trên đĩa. Trong engine của lab, vacuum
không tìm thấy file do writer crash trước commit; expiry Iceberg cũng chưa
tự dọn manifest lists. Vì vậy tôi sẽ theo dõi số file, kích thước trung bình,
bytes đã tombstone và độ trễ reader; lên lịch maintenance theo số đo.

Retention phải dài hơn reader/job cần bảo vệ. Chỉ dùng retention 0 trên
scratch; production cần dry-run, age guard và kiểm tra tất cả snapshot còn
được giữ trước khi xóa.

AI hỗ trợ thực thi và soạn bản reflection này; phạm vi được khai tại
[AI_USAGE.md](AI_USAGE.md). Người nộp cần đọc lại và tự giải thích kết quả.
