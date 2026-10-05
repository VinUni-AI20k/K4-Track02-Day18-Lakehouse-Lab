# Khai báo sử dụng AI

**Công cụ:** Claude Code (Anthropic, model Claude Opus 5.5), chạy trong terminal trên máy cá nhân.

**Phạm vi hỗ trợ:**

- Đọc README/docs/source code và lập danh sách việc cần làm của lab.
- Hướng dẫn lệnh cài đặt trên Windows (cmd), sửa lỗi venv chưa cài dependencies.
- Chạy `verify_lite.py`, `pytest`, `run_all.py` và thực thi 8 notebook trên máy của tôi; mọi số liệu
  trong notebook/screenshot là output thật của các lần chạy đó, không có số liệu nào được nhập tay.
- Thêm kiểm tra chặt hơn ở NB1 (cờ schema enforcement không còn hardcode) và NB4 (assert chất lượng Gold).
  Không hạ ngưỡng hay xoá assertion nào.
- Soạn nháp các cell "📝 Giải thích kết quả" dựa trên output thực tế, và phát hiện/giải thích một số chi tiết
  của output (Gold có 8 ngày do múi giờ UTC+7; "5 files" ở NB6 gồm 2 checkpoint tự động; dòng "0 B" ở VACUUM dry-run).
- Chụp screenshot từ các cell output đã lưu; soạn nháp `INFO.md` và `REFLECTION.md`.

**Phần tôi tự chịu trách nhiệm:** đọc lại, kiểm tra và có thể giải thích toàn bộ code, số liệu và phần giải thích
trong bài nộp; chỉnh sửa reflection theo quan điểm của bản thân.
