# REFLECTION

Anti-pattern nguy hiểm nhất tôi gặp ở lab này là **quên dọn dữ liệu cũ** — thứ không ai nhìn thấy.

Hệ thống tôi quan tâm lưu câu hỏi và câu trả lời giữa người dùng với mô hình AI, mỗi ngày hàng triệu bản ghi:

* **Nhiều file nhỏ, bản cũ chưa dẹp.** Mỗi lần ghi một file riêng; hàng trăm nghìn file thì mỗi câu hỏi phải đọc hết — tốn tiền. Bản cũ nằm lại vẫn bị tính tiền.
* **Bản sao bên ngoài lệch dữ liệu.** Xoá dữ liệu một người dùng ở bản chính, nhưng bản sao lưu "gợi ý tìm kiếm" vẫn còn — hệ thống vẫn trả được dữ liệu cần xoá.

Rút ra: phần lớn sự cố đến từ việc không ai dọn sau khi ghi chứ không phải từ mã lỗi. Cách chữa là quy trình: dọn tự động theo lịch, đặt thời hạn lưu rõ ràng, ghi lại mọi thao tác xoá. Với dữ liệu cá nhân, đó còn là nghĩa vụ pháp lý.

**AI:** tôi dùng AI để giải thích khái niệm, đọc mã và soạn văn bản; số liệu do tôi tự chạy. Xem AI_USAGE.md.
