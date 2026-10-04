# Reflection

Anti-pattern dễ gặp nhất với hệ thống LLM/agent tôi quan tâm là small files do
streaming ingest. Mỗi request hoặc bước tool tạo một bản ghi nhỏ; nếu ghi một
commit cho từng nhóm rất ít dòng, số file và metadata tăng nhanh dù dung lượng
dữ liệu chưa lớn. Truy vấn dashboard phải mở nhiều file và lập kế hoạch lâu hơn.

NB6 cho thấy 200 file giảm còn 11 sau compaction, trong khi 100.000 dòng vẫn
được giữ. Z-order giúp query một user chỉ cần cân nhắc 1/10 file. Điều này cho
thấy cần quản lý số file và chất lượng stats, không chỉ tổng GB.

Tôi sẽ gom micro-batch theo dung lượng/thời gian phù hợp, đo file count và kích
thước trung bình, rồi lên lịch compaction, clustering, expiry và orphan removal.
Retention phải bảo vệ reader, writer và nhu cầu replay; không dùng retention 0
như bảng scratch của lab trong hệ thống thật. External vector index cũng cần
nhận delete events để tránh dữ liệu đã xóa vẫn xuất hiện khi retrieval.

AI hỗ trợ soạn bản nháp này và thực thi lab; phạm vi chi tiết: [AI_USAGE.md](AI_USAGE.md).
