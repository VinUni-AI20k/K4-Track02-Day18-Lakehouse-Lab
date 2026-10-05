# Reflection: Anti-Pattern Trong Lakehouse

Một anti-pattern phổ biến và nguy hiểm nhất mà tôi quan tâm trong các hệ thống Lakehouse là **Small-File Problem (bệnh quá nhiều file nhỏ)** sinh ra từ streaming ingestion (Kafka/CDC) hoặc micro-batch ghi liên tục.

Hệ thống ghi hàng ngàn file chỉ vài chục KB. Điều này không làm tăng dung lượng lưu trữ đáng kể, nhưng làm bùng nổ chi phí truy vấn phi tuyến tính do chi phí HTTP GET trên S3 và làm sập bộ nhớ của Query Engine khi phải quét cây metadata khổng lồ để lập kế hoạch (scan planning). Hơn nữa, Z-order hoàn toàn mất tác dụng skipping nếu không có compaction hợp lý.

**Cách phòng tránh:**
1. Thiết lập ngưỡng buffer tối thiểu ở tầng writer (ví dụ: trigger interval hợp lý hoặc batch size ≥ 100 MB).
2. Tự động hóa Job 1 (Compaction / `OPTIMIZE`) định kỳ theo FinOps schedule để gộp file về kích thước tối ưu (128–512 MB).
3. Luôn đi kèm Job 3 (Vacuum / Snapshot Expiry) để thu hồi dung lượng từ các file tombstoned.

*Phạm vi sử dụng AI:* Xem chi tiết tại [AI_USAGE.md](AI_USAGE.md).
