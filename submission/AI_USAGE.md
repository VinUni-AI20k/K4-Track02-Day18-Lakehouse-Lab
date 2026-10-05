# Khai báo sử dụng AI

**Công cụ:** Claude Code (Anthropic, model Claude Opus 5.5) chạy trong VS Code trên máy cá nhân.

## AI đã làm gì

| Việc | Phạm vi |
|---|---|
| Đọc repo và giải thích yêu cầu | Đọc README, docs/, 8 notebook, scripts, tests; tóm tắt cái cần nộp |
| Cài môi trường và chạy kiểm tra | Tạo `.venv` (Python 3.11), chạy smoke, sinh dữ liệu, pytest, `run_all.py`, thực thi 8 `.ipynb` bằng `nbconvert --execute` trên máy này |
| Sửa mã notebook | 3 thay đổi chỉ thêm bằng chứng (NB1, NB4, NB6), liệt kê trong [INFO.md](INFO.md); không bỏ assertion, không hạ ngưỡng |
| Phân tích output | Tìm nguyên nhân 3 chỗ output dễ đọc sai: "5 files" ở NB6 (2 là checkpoint), checkpoint in ra là bản cũ nhất, Gold có 8 ngày do múi giờ DuckDB (UTC+7). Mỗi nguyên nhân được kiểm chứng bằng lệnh riêng trước khi ghi vào giải thích |
| Viết giải thích | Soạn các ô Markdown "Giải thích kết quả" trong notebook nộp, dựa trên số liệu của lần chạy này |
| Screenshots | Render notebook đã thực thi sang HTML và chụp bằng Chrome headless (Playwright); ảnh là output thật, không chỉnh sửa |
| Reflection và bonus | Soạn bản nháp `REFLECTION.md` và `bonus/ARCHITECTURE.md` |

## Cam kết

- Mọi số liệu trong notebook, screenshots và giải thích đến từ lần chạy thật trên máy này
  (05/10/2026); không có output được tạo tay.
- Tôi đã đọc lại các giải thích, reflection và bonus, và chịu trách nhiệm giải thích được mã nguồn
  cùng kết quả khi được hỏi.
- Các ước lượng giá trong bonus là giả định, đã ghi rõ ngay trong tài liệu.
