# Reflection

Anti-pattern tôi chọn phân tích là bỏ maintenance trong lakehouse LLM observability. Mỗi micro-batch tạo thêm file nhỏ; truy vấn dashboard phải mở nhiều file, đọc nhiều metadata và khó skip khi min/max chồng lấn. Trong NB6, compaction và clustering xử lý hai vấn đề khác nhau: giảm số file và thu hẹp vùng dữ liệu mỗi file.

Tôi sẽ theo dõi active file count, kích thước file, bytes tombstoned, tuổi orphan và consumer lag. Cần lịch compaction, clustering, snapshot expiry và orphan sweep có age guard. Kết quả lab cho thấy snapshot đã hết tham chiếu chưa đồng nghĩa file vật lý đã mất. Retention phải bảo vệ reader, writer và version training được pin; VACUUM 0 chỉ phù hợp scratch của bài lab.

Codex hỗ trợ đọc đề, chỉnh kiểm tra, chạy notebook trên máy, thu bằng chứng và soạn bản reflection/bonus; phạm vi đầy đủ ở [AI_USAGE.md](AI_USAGE.md). Người nộp cần tự đọc, chạy lại và điều chỉnh reflection theo hiểu biết trước khi gửi bài.
