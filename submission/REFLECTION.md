# Reflection (≤ 200 từ)

Khi nghĩ về hệ thống ghi log cho các lần gọi LLM, tôi lo nhất là tạo ra quá nhiều file nhỏ. Request thường đến liên tục, đôi lúc tăng vọt; nếu mỗi đợt ghi hoặc lần retry lại sinh một file Parquet riêng, dữ liệu sẽ nhanh chóng bị chia vụn. Dashboard khi ấy phải dò qua nhiều file và metadata, còn chi phí lưu trữ cũng tăng theo số lượng object. Trong lab, compaction gom 200 file thành 55, còn Z-order giúp truy vấn theo `user_id` bỏ qua được nhiều file hơn. Nếu áp dụng vào hệ thống thật, tôi sẽ gom dữ liệu thành các batch đủ lớn, theo dõi kích thước và số file theo partition, rồi compaction khi cần. Tôi chỉ thêm clustering/Z-order sau khi xem workload thực tế; chia partition quá nhỏ có thể làm tình hình tệ hơn.

Tôi có dùng OpenAI Codex để hiểu yêu cầu lab, phân tích output và chỉnh phần giải thích. Số liệu trong notebook lấy từ kết quả chạy, không phải số minh họa. Phạm vi hỗ trợ được ghi trong `AI_USAGE.md`.
