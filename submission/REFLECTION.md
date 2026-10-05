# Reflection

Anti-pattern dễ gặp nhất với hệ thống LLM observability là **small files không được maintenance**. Log inference/agent trace thường đến từ streaming với trigger ngắn, mỗi micro-batch ghi một file nhỏ. Nếu chỉ nhìn số dòng thì pipeline có vẻ đúng, nhưng query dashboard, replay, training data scan và cost sẽ xấu vì engine phải plan và mở quá nhiều file. NB2 và NB6 cho thấy compaction/Z-order/checkpoint không phải tối ưu phụ, mà là việc vận hành bắt buộc. Cách phòng tránh là thiết kế batch interval hợp lý, đặt cron compaction và clustering, theo dõi file count/average file size, và chạy vacuum/orphan removal có retention guard rõ ràng.

Em dùng AI/Codex để đọc source, cài môi trường, chạy notebook/test và tạo cấu trúc submission. Không dùng AI để tạo output giả hoặc hạ ngưỡng assertion.
