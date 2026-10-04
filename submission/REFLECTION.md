# Reflection: Blind Vacuuming & Orphan Accumulation

Trong các hệ thống streaming ingestion và LLM traces mà tôi quan tâm, anti-pattern dễ mắc nhất là **"Blind Vacuuming & Orphan Accumulation"**.

Nhiều đội ngũ mặc định chạy `VACUUM` là dọn sạch bộ nhớ. Tuy nhiên, qua thực nghiệm NB6, `deltalake` (Rust) chỉ thu hồi file đã được ghi nhận *tombstone* trong transaction log. Khi writer gặp crash, các file Parquet mồ côi (uncommitted orphans) bị bỏ lại trên object storage nhưng không nằm trong log, khiến `VACUUM` hoàn toàn bỏ qua. Theo thời gian, hàng triệu file rác tích tụ gây lãng phí lớn chi phí S3/GCS. Ngược lại, nếu lạm dụng `VACUUM` với retention quá ngắn trên môi trường concurrent, hệ thống sẽ xóa nhầm file đang ghi của writer khác gây hỏng dữ liệu.

**Giải pháp:** Kết hợp `VACUUM` log-based với tiến trình audit: tính hiệu tập hợp (physical files \ log files) kèm age guard an toàn (> 24h) trước khi xóa.

*(Kê khai AI: Sử dụng Gemini / Antigravity hỗ trợ rà soát rubric, code trực quan hóa và kiểm thử. Xem chi tiết tại [AI_USAGE.md](AI_USAGE.md)).*
