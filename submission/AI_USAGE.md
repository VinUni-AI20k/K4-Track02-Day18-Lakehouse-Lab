# Khai báo sử dụng AI

**Công cụ:** Claude Code (model Claude Opus 5.5), chạy trong ứng dụng Claude desktop.

**Phạm vi hỗ trợ:**
- Fork/clone repo, tạo `.venv`, cài dependencies, chạy smoke test, sinh dữ liệu, chuyển `.py` → `.ipynb`.
- Thực thi 8 notebook bằng Jupyter kernel (`jupyter nbconvert --execute`), chạy `pytest` và `run_all.py`.
- Phát hiện và đề xuất sửa hai chỗ trong mã notebook (NB1: cờ enforcement hardcode; NB4: ranh giới ngày phụ thuộc múi giờ máy, kèm cell kiểm tra hợp đồng Gold).
- Nháp các cell "Kết quả & giải thích", `REFLECTION.md`, `bonus/ARCHITECTURE.md` và PoC.
- Chụp ảnh các cell kết quả từ notebook đã render (Playwright + Edge).

**Phần tôi tự kiểm chứng:** mọi số liệu trong phần giải thích đều lấy từ output thật của notebook đã nộp. Tôi đã đọc lại từng giải thích và đối chiếu với RUBRIC/CHECKPOINTS. Hai thay đổi mã được tôi kiểm tra lại bằng output: version bảng 0 → 0 khi ghi sai kiểu; truy vấn so `CAST(ts AS DATE)` theo múi giờ cục bộ và theo UTC (8 so với 7 ngày).

Không có output nào bị sửa tay hay làm giả. Không dùng dữ liệu thật hay secrets.
