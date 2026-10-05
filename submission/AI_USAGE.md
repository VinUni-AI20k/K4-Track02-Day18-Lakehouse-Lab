# Khai sử dụng AI

Theo [RULES.md](../docs/RULES.md): được dùng AI để giải thích khái niệm, đọc
code, tìm nguyên nhân lỗi và đề xuất sửa; người nộp phải tự chạy, tự kiểm tra
và giải thích được kết quả của mình.

> Sửa bảng dưới cho đúng thực tế của bạn trước khi nộp: giữ dòng đúng, xoá
> dòng không đúng, bổ sung việc bạn đã nhờ AI làm thêm.

| Phạm vi | Công cụ | Mô tả |
|---|---|---|
| Lập kế hoạch làm bài | Arena.ai Agent Mode | Tóm tắt quy trình theo đề bài thành checklist: thứ tự notebook, ngưỡng rubric của từng NB, bằng chứng cần chụp, câu hỏi cần trả lời (`docs/HUONG-DAN-LAB.md`) |
| Tiện ích kiểm tra bài nộp | Arena.ai Agent Mode | Viết `scripts/check_submission.py` — script chỉ đọc, cảnh báo thiếu notebook/thiếu output/thiếu ảnh/reflection quá 200 từ |
| Giải thích khái niệm | Arena.ai Agent Mode | `<điền nếu có: schema enforcement vs evolution, Z-order và file skipping, snapshot expiry vs orphan removal …>` |
| Gỡ lỗi khi chạy | Arena.ai Agent Mode | `<điền nếu có, ví dụ: lỗi kernel/encoding/cast FLOAT[256]>` |
| Chạy notebook, đọc kết quả, viết giải thích và reflection | — (tự làm) | Mọi số liệu trong notebook là kết quả chạy trên máy tôi; phần diễn giải và reflection do tôi tự viết |

Không dùng AI để tạo output giả, không hạ ngưỡng hay bỏ assertion để báo PASS,
không gửi secrets/dữ liệu riêng tư vào prompt.