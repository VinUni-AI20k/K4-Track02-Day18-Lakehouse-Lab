# Reflection

Anti-pattern mình chọn là dùng Bronze làm nguồn truy vấn dashboard. Với log LLM, mỗi request còn chứa JSON thô và prompt/response lớn; truy vấn chi phí, latency hoặc lỗi phải parse lặp lại payload, đọc nhiều dữ liệu không cần thiết và dễ lộ nội dung nhạy cảm. Kết quả lab cho thấy Bronze có 200.000 dòng, trong khi Silver chuẩn hóa và giảm còn 190.052; Gold chỉ cần 21 nhóm ngày × model để trả các metric cần theo dõi. Mình sẽ giữ payload trong Bronze với retention ngắn, khử trùng và chuẩn hóa ở Silver, rồi tổng hợp Gold theo dimensions của dashboard. Dashboard đọc Gold; clustering theo tenant/model và theo dõi freshness, scan bytes, error rate giúp phát hiện khi pipeline hoặc layout làm truy vấn tốn kém trở lại.

Phạm vi sử dụng AI: [AI_USAGE.md](AI_USAGE.md).


