# Khai báo sử dụng AI

Công cụ: **Claude Code** (Anthropic), dùng trong VS Code.

AI đã hỗ trợ:

- Tạo venv, cài dependencies, chạy smoke test, pytest và `run_all.py`.
- Chuyển 8 notebook sang `.ipynb`, thực thi headless và chép vào `submission/notebooks/`.
- Thêm cell bằng chứng `_delta_log/` (NB1), cell kiểm tra Gold (NB4) và soạn nháp các cell "Giải thích kết quả".
- Chụp screenshot từ HTML export của notebook đã chạy.
- Soạn nháp `INFO.md`, `REFLECTION.md` và file này.
- Bonus: soạn nháp `bonus/ARCHITECTURE.md` (Topic A) và viết, chạy PoC `bonus/poc/pii_retention_poc.py`. Các giá cloud và giả định throughput trong bài là ước tính, đã đánh dấu *(GĐ)*.

Mọi số liệu trong phần giải thích lấy từ output thực tế của lần chạy trên máy cá nhân;
không có output nào bị chỉnh tay hay bỏ kiểm tra. Tôi đã đọc lại, đối chiếu với
[RUBRIC.md](../docs/RUBRIC.md) và chịu trách nhiệm về nội dung bài nộp.
