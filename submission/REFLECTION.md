# Reflection

Anti-pattern được chọn là ghi nhiều file nhỏ mà không theo dõi maintenance. Trong pipeline LLM observability của lab, các đợt ghi nhỏ giúp dữ liệu xuất hiện nhanh nhưng làm tăng số file, chi phí mở file và đọc metadata. Dashboard có thể chậm dù tổng dung lượng chưa lớn.

NB2 cho thấy 200 file giảm còn 55; thời gian truy vấn median giảm từ 492,3 xuống 34,2 ms sau compaction và Z-order. Hai thao tác giải quyết vấn đề khác nhau: compaction giảm overhead file, còn Z-order giúp thống kê min/max loại file không phù hợp.

Cách phòng tránh là điều chỉnh kích thước batch, theo dõi số file và kích thước trung bình, rồi lên lịch compaction theo ngưỡng. Cần đo cả latency lẫn pruning, giữ retention đủ cho reader và time travel, và kiểm tra tham chiếu trước khi dọn orphan. Không dùng retention 0 cho dữ liệu cần giữ.

Codex hỗ trợ thực thi, đọc output và soạn phần giải thích/reflection; phạm vi được khai trong [AI_USAGE.md](AI_USAGE.md). NB6–NB8 đã hoàn tất các assertion gốc.
