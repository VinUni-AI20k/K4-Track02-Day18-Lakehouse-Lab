# Reflection: Small-File Problem in Streaming Ingestion

Trong các hệ thống AI/LLM Observability hoặc IoT streaming, dữ liệu thường được micro-batch và ghi liên tục sau mỗi vài giây (như mô phỏng ở NB2 và NB6). Hệ quả là sinh ra hàng chục nghìn small files (vài chục KB) trên Object Storage.

Anti-pattern này gây ra hai tổn thất lớn:
1. **Truy vấn chậm & tốn kém:** Engine phải gửi hàng triệu API GET/LIST requests thay vì đọc streaming tuần tự; chi phí scan trên S3/MinIO tăng vọt.
2. **Metadata tax cao:** Transaction log (JSON/Avro) phình to gấp nhiều lần dung lượng dữ liệu thực tế (ở NB5 metadata chiếm tới 290% data size), làm nghẽn metadata planning.

**Giải pháp phòng tránh:**
- Tối ưu writer trigger interval (gom batch tối thiểu 128MB–512MB).
- Định kỳ chạy compaction: `dt.optimize.compact()` kết hợp Z-order theo cột hay filter (`user_id`, `model`) để hỗ trợ min/max stats file skipping.
- Tự động hóa `VACUUM` có age guard và checkpointing định kỳ nhằm dọn dẹp tombstone files mà không ảnh hưởng active readers.

*(Chi tiết dùng AI tại [AI_USAGE.md](AI_USAGE.md))*
