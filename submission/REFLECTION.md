# Reflection — Small-file problem trong hệ thống LLM/AI app

Hệ thống tôi quan tâm là ứng dụng LLM: log mọi prompt/response, trace của agent và embeddings cho RAG.
Anti-pattern dễ vướng nhất là **small-file problem**. Log LLM đến liên tục, mỗi request vài KB. Muốn
dashboard cost/latency cập nhật nhanh thì phải commit thường xuyên.

Lab cho thấy rõ cái giá: NB6 tạo 200 file trung bình 51.5 KB. Compaction đưa về 11 file (18×), Z-order cho phép
bỏ qua 90% file khi query một user. NB2 đo pruning 55× sau Z-order. NB5 cho thấy metadata có thể lớn gấp 2.9 lần dữ liệu khi file quá nhỏ.

Cách phòng tránh: commit micro-batch (~60 giây) thay vì theo từng request. Lên lịch compaction cho partition
đã "nguội". Cluster theo cột hay lọc nhất (tenant, user). Luôn chạy expiry kèm orphan sweep, vì NB6 chứng minh
VACUUM và `expire_snapshots` không tự dọn hết. Cảnh báo khi file trung bình quá nhỏ.

**Khai báo AI:** tôi dùng Claude Code để hỗ trợ cài môi trường, chạy notebook, nháp phần giải thích và bonus.
Chi tiết ở [AI_USAGE.md](AI_USAGE.md).
