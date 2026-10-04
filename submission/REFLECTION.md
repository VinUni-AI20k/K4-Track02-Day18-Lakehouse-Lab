# Reflection: Anti-Pattern Trong Data Lakehouse

**Anti-pattern lựa chọn:** *Small-File Syndrome & Hiểu lầm về VACUUM khi Streaming Ingestion.*

Trong hệ thống theo dõi và ghi log LLM (hàng triệu requests/giờ), việc ghi liên tục qua micro-batching tạo ra hàng trăm nghìn file Parquet nhỏ (vài KB). Điều này làm bùng nổ metadata, khiến thời gian scan và chi phí đọc dữ liệu tăng vọt. Nghiêm trọng hơn, đội ngũ vận hành thường lầm tưởng lệnh `VACUUM` sẽ tự động dọn sạch mọi file rác. Thực tế trong Delta Lake và Iceberg (như đã đo tại NB6), `VACUUM` chỉ xóa các file đã được ghi nhận trong transaction log (tombstone); các file do writer crash bỏ lại (orphan files) không bao giờ bị dọn nếu chỉ gọi `VACUUM` thông thường, gây lãng phí dung lượng lưu trữ và chi phí S3.

**Cách phòng tránh:**
1. Áp dụng cơ chế **Micro-compaction** định kỳ kết hợp Z-Order theo `tenant_id` để gộp file nhỏ về kích thước chuẩn (128MB–256MB).
2. Thiết lập job bảo trì độc lập để rà soát và xóa **Orphan Files** (so sánh file vật lý trên object storage với transaction log/manifest), kết hợp cấu hình Snapshot Expiry hợp lý.

*(Chi tiết khai báo công cụ và phạm vi sử dụng AI xem tại [AI_USAGE.md](AI_USAGE.md)).*
