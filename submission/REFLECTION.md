# Reflection

**Anti-pattern: small-file problem (kèm orphan files).**

Ở NB4 xử lý log LLM observability: 200,000 request, nhiều lần ghi nhỏ từ pipeline streaming. Loại dữ liệu này dễ gặp small files, vì mỗi lần ghi chỉ thêm ít dòng. NB6 cho thấy hậu quả: 200 file trung bình 51.5 KB, và nhiều commit làm log phình ra. Compaction đưa về 11 file (giảm 18×) và clustering giúp truy vấn point chỉ mở 1/10 file.

NB6 cũng cho thấy một writer bị crash để lại orphan file mà `VACUUM` của `deltalake` không dọn, vì log chưa từng biết đến chúng. Với Iceberg, `expire_snapshots` chỉ giảm snapshot (20 → 3), còn file avro vẫn là 40 cho tới khi dọn orphan.

Cách phòng tránh: tăng trigger interval hoặc gom batch trước khi ghi; lên lịch compaction, expiry và dọn orphan (có age guard) như một chuỗi; đặt retention dài hơn query chạy lâu nhất.

**AI:** dùng Claude Code để chạy lại notebook, giải thích kết quả và soạn nháp các ô markdown; đã đọc và kiểm tra số liệu trên output của chính mình. Chi tiết ở [AI_USAGE.md](AI_USAGE.md).
