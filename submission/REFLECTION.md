# Reflection

Anti-pattern tôi thấy dễ gặp nhất là **small files**. Pipeline ghi dữ liệu quá
thường xuyên có thể tạo hàng nghìn file nhỏ dù từng lần ghi đều đúng. Khi đó
chi phí metadata, số lần mở object và thời gian lập kế hoạch tăng; truy vấn
cũng khó tận dụng file pruning.

Với log hoặc LLM observability, dữ liệu đến liên tục nên nguy cơ này khá thực
tế. Cách phòng tránh là gom batch theo kích thước hoặc thời gian hợp lý, theo
dõi số file và kích thước trung bình, rồi chạy compaction định kỳ. Nếu truy vấn
lọc theo `user_id`, clustering hoặc Z-order giúp min/max statistics skip file.
Vacuum và orphan sweep cần retention an toàn để không xóa dữ liệu reader cũ còn
cần.

Day18 khá rộng nên tôi chưa hiểu sâu toàn bộ cơ chế ngay lần đầu. Tôi đã chạy
và kiểm tra các notebook, đồng thời sẽ tiếp tục đọc thêm về Delta, Iceberg và
catalog. GitHub Copilot hỗ trợ đọc code, phân tích lỗi và diễn giải output; tôi
chịu trách nhiệm chạy, kiểm tra và nộp kết quả.
