# Khai báo sử dụng AI

**Công cụ:** Claude Code (Anthropic, model Claude Opus 5.5) chạy trong VS Code trên máy cá nhân.

## AI đã làm gì

| Việc                           | Phạm vi                                                                                                                                                                                                                             |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Đọc repo và giải thích yêu cầu | Đọc README, docs/, 8 notebook, scripts, tests; tóm tắt cái cần nộp                                                                                                                                                                  |
| Sửa mã notebook                | 3 thay đổi chỉ thêm bằng chứng (NB1, NB4, NB6), liệt kê trong [INFO.md](INFO.md); không bỏ assertion, không hạ ngưỡng                                                                                                               |
| Phân tích output               | Tìm nguyên nhân 3 chỗ output dễ đọc sai: "5 files" ở NB6 (2 là checkpoint), checkpoint in ra là bản cũ nhất, Gold có 8 ngày do múi giờ DuckDB (UTC+7). Mỗi nguyên nhân được kiểm chứng bằng lệnh riêng trước khi ghi vào giải thích |

## Cam kết

- Tôi đã đọc lại các giải thích, reflection và bonus, và chịu trách nhiệm giải thích được mã nguồn
  cùng kết quả khi được hỏi.
- Các ước lượng giá trong bonus là giả định, đã ghi rõ ngay trong tài liệu.
