# Reflection — Lakehouse Anti-Pattern

Anti-pattern tôi quan tâm nhất là để dữ liệu streaming tạo ra quá nhiều small files nhưng không có lịch maintenance. Với hệ thống LLM observability, mỗi micro-batch đều hợp lệ; tuy nhiên hàng trăm file nhỏ làm tăng chi phí list/GET, metadata planning và latency truy vấn. Vấn đề thường chỉ lộ rõ khi dashboard chậm, lúc đó compaction phải rewrite nhiều dữ liệu và tạm thời tăng dung lượng lưu trữ.

Tôi sẽ phòng tránh bằng cách đặt kích thước batch và target file hợp lý ngay từ ingestion, theo dõi file count/average file size, rồi chạy compaction và clustering theo lịch. Snapshot expiry, orphan sweep và checkpoint cũng cần là các job độc lập có metric trước/sau, thay vì giả định VACUUM tự dọn mọi loại file. Với truy vấn hot, tôi sẽ phân vùng theo thời gian và cluster theo tenant hoặc user key để file statistics giúp pruning hiệu quả.

AI được dùng để hỗ trợ đọc code, giải thích khái niệm, chẩn đoán lỗi môi trường và kiểm tra kết quả; tôi tự chạy, kiểm tra và đối chiếu output.
