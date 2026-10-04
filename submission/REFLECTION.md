# Lakehouse Reflection

**Anti-pattern:** *Small-File Problem & Thiếu Job Maintenance Tự Động.*

Trong hệ thống xử lý log telemetry và API LLM quy mô lớn (hàng nghìn request/giây), việc streaming micro-batch liên tục trực tiếp vào object storage mà không nén gộp file dẫn tới hàng trăm nghìn file Parquet nhỏ (vài KB). Hậu quả là bùng nổ chi phí request GET/LIST trên Cloud Storage, metadata bloat làm tê liệt query planning và dashboard suy giảm hiệu năng nghiêm trọng.

**Giải pháp phòng tránh:**
1. **Thiết lập chu kỳ Maintenance bắt buộc:** Lập lịch định kỳ chạy `OPTIMIZE compact` (target size 128–512 MB), `Z-ORDER` theo `tenant_id/ts`, và `VACUUM` với retention an toàn (7 ngày).
2. **Buffer tầng Ingestion:** Gom micro-batch từ 1–5 phút tại message queue/gateway trước khi ghi xuống storage thay vì ghi phân tán từng giây.
3. **Giám sát FinOps:** Đặt ngưỡng cảnh báo tỷ lệ metadata:data và số lượng request I/O trên S3/MinIO.

*Khai báo AI:* Sử dụng AI hỗ trợ phân tích và định dạng; chi tiết tại [AI_USAGE.md](AI_USAGE.md).
