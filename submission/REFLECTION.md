# Reflection

Anti-pattern tôi chọn là xem external vector index như system of record. Cách này
phổ biến trong RAG vì truy vấn nhanh, nhưng tách lifecycle embedding khỏi dữ liệu
gốc. NB7 cho thấy sau yêu cầu xóa, lakehouse trả 0 hit trong khi index cũ vẫn trả 8
hit. Ứng dụng vì thế còn có thể đưa nội dung đã xóa vào prompt.

Tôi sẽ giữ lakehouse làm system of record, coi index là artifact có thể tái tạo và
lưu version nguồn khi build. Pipeline index phải đọc Change Data Feed, xử lý delete
như sự kiện bắt buộc, có checkpoint/idempotency và đối soát ID định kỳ. Cần cảnh báo
khi độ trễ CDF hoặc số ID lệch vượt ngưỡng. Quy trình xóa chỉ hoàn tất sau khi xác
nhận cả bảng, index, cache và artifact dẫn xuất.

Tôi dùng OpenAI Codex để rà rubric, chạy kiểm thử, tổ chức artifact và hỗ trợ diễn
giải; chi tiết ở AI_USAGE.md. Toàn bộ số đo là output chạy cục bộ.
