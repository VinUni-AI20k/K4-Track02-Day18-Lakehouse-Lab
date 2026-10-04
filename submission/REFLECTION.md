# Reflection: Top Lakehouse Anti-Patterns

**Anti-pattern nguy hiểm nhất:** *Small-File Problem & Zombie Orphan Accumulation* do Streaming Ingestion.

**Hệ thống quan tâm:** Nền tảng LLM Observability / API Gateway ghi nhận hàng triệu request mỗi ngày.

**Vì sao dễ vướng:**
Các microservices đẩy payload telemetry (prompt, completion, latency) liên tục theo batch nhỏ (vài giây/lần) để làm tươi dashboard. Việc ghi vi mô này sinh ra hàng trăm nghìn file Parquet kích thước chỉ vài chục KB. Hệ quả là metadata bùng nổ, query scan chậm hàng chục lần do chi phí mở kết nối/I/O, và hóa đơn S3 ListObjects tăng vọt. Nguy hiểm hơn, khi writer process bị crash giữa chừng do OOM hoặc rớt mạng, các file Parquet dở dang chưa kịp commit vào transaction log sẽ trở thành *zombie orphans*. Lệnh `VACUUM` mặc định chỉ dọn các file có tombstone trong log, hoàn toàn "mù" trước các orphan này, âm thầm gây lãng phí dung lượng lưu trữ khổng lồ.

**Cách phòng tránh:**
1. Đệm dữ liệu qua Kafka/staging buffer (micro-batch 5–10 phút) trước khi ghi vào Bronze.
2. Lập lịch bảo trì tự động: Auto-compaction & Z-Order hàng ngày gom file về kích thước tối ưu 128–256 MB.
3. Triển khai script quét hiệu tập hợp (`physical_storage - delta_log_commits`) để dọn sạch orphan chưa commit.
