# AI_USAGE

## Tổng quan

Bài lab được thực hiện chủ yếu bằng công sức cá nhân: cài môi trường, chạy script và test, thực thi notebook, đọc và kiểm tra kết quả, chụp ảnh bằng chứng, nộp bài. AI (Claude) giữ vai trò hỗ trợ: giải thích đề bài, gợi ý cách kiểm tra và soạn nháp văn bản để chỉnh sửa lại.

## Phần thực hiện trực tiếp

- Fork repo, đổi tên đúng mẫu, clone và thiết lập môi trường (`.venv`, `requirements.txt`).
- Chạy `verify_lite.py`, `generate_data_lite.py`, `generate_ai_data.py`, `pytest` và `run_all.py` trên Windows.
- Chuyển 8 file `.py` sang `.ipynb` bằng jupytext, mở notebook trong Jupyter Lab.
- Đọc output từng notebook, đối chiếu với ngưỡng trong RUBRIC.md.
- Chụp toàn bộ ảnh trong `submission/screenshots/`.
- Xem lại và chỉnh sửa `INFO.md`, `REFLECTION.md` cùng các Markdown cell trước khi nộp.
- `git add`, `git commit`, `git push` và mở PR do chính chủ bài làm thực hiện.

## Phần AI hỗ trợ

- Giải thích yêu cầu của đề và các khái niệm (Delta log, Z-order, Iceberg field ID, orphan files...).
- Gợi ý cách kiểm tra những điểm notebook không tự assert (NB1: lỗi ghi sai kiểu; NB4: Gold).
- Hỗ trợ chạy `nbconvert` để lưu output vào notebook, theo lệnh được giao.
- Soạn nháp Markdown cell giải thích số liệu.
- Hướng dẫn cách chụp ảnh và tìm đúng cell cần chụp.

## Tuyên bố

- Mã nguồn notebook gốc, script và test không bị chỉnh sửa; không hạ ngưỡng hay bỏ assertion.
- Mọi con số trong bài lấy từ output thật đã chạy.
- AI không tự commit, push hay nộp bài thay.