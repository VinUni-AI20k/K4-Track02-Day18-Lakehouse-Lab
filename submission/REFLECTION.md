# Reflection — Small-file problem khi ingest log LLM

Trong Top 5 Lakehouse Anti-Patterns, hệ thống tôi quan tâm — log gọi LLM cho observability
(như NB4) — dễ vướng nhất **small-file problem do streaming mà không có maintenance**.

Vì sao: log được đẩy theo micro-batch vài giây để dashboard gần real-time. Mỗi commit đều đúng,
nhưng tích lũy thành hàng nghìn file vài chục KB. NB6 đo đúng điều này: 200 commit tạo 200 file
~51 KB; compaction đưa về 11 file (18×). NB2 cho thấy khi chưa clustering, stats min/max chồng
nhau nên point query phải mở mọi file; sau Z-order chỉ còn 1/55 file. Expiry cũng không tự giải
phóng storage: Iceberg giảm 20 → 3 snapshot nhưng 40 file avro vẫn còn, phải sweep riêng.

Phòng tránh: chọn trigger interval và target file size hợp lý ở writer; lên lịch compaction +
Z-order theo cột lọc chính, vacuum/expiry với retention ≥ 7 ngày, orphan sweep có age guard,
checkpoint; cảnh báo theo số file và kích thước file trung bình.

**AI:** dùng Claude Code để cài môi trường, chạy notebook và viết nháp giải thích; chi tiết ở
[AI_USAGE.md](AI_USAGE.md).
