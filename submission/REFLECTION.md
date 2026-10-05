# Reflection — Bùi Thị Thu Uyên (2A202602613)

**Anti-pattern: small files và không có lịch maintenance.**

Hệ thống mình quan tâm là log quan sát LLM (latency, token, cost), được ghi liên tục theo micro-batch. Từng commit
đều đúng, nhưng tích lũy lại thành rất nhiều file nhỏ. NB6 tái hiện đúng tình huống này: 200 commit tạo ra 200 file,
trung bình 51.5 KB mỗi file. Mỗi query phải GET từng file, planner phải đọc thêm metadata (NB5: metadata bằng 284% data).
Sau compaction và Z-order, số file giảm 18× và point query bỏ qua được 90% file.

Bẫy thứ hai là nghĩ rằng chạy một lệnh là đủ. Trong lab, VACUUM của `deltalake` không thấy orphan chưa commit, còn
`expire_snapshots` của PyIceberg không xóa file vật lý, nên storage không giảm.

Cách phòng tránh: gom batch ngay ở writer; lên lịch đủ compaction, clustering, expiry, quét orphan có điều kiện tuổi file,
và checkpoint; theo dõi kích thước file trung bình, cảnh báo khi file nhỏ hơn nhiều so với mục tiêu 128–512 MB.

**AI:** dùng Claude Code để chạy lab, tìm lỗi đo đạc và soạn nháp giải thích. Chi tiết: [AI_USAGE.md](AI_USAGE.md).
