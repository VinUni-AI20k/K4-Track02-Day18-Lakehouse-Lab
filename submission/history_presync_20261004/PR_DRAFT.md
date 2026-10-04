# Bản nháp PR — chưa gửi

Tiêu đề dự kiến:

`[K4-Track02-Day18] DuongXuanVinh - 2A202602622 - Lakehouse Lab`

Họ tên: Dương Xuân Vinh. MSSV: 2A202602622. Đường chạy: lightweight, Python 3.14.7 trên Windows 11.

Cả 8 notebook đã có output hoàn tất. NB6 VACUUM thu hồi ròng 16.907.155 byte, xóa 3 orphan, Iceberg 20 → 3 snapshots và sweep 17 manifest lists; 9 assertion gốc PASS. NB7 chứng minh 0 hits in-table/8 hits external và 8 CDF delete events; NB8 chứng minh user_007 từ 8 xuống 0. Hai notebook này giữ version trước để phục hồi; NB6 đã thực hiện tradeoff retention như đề bài.

Bài làm gồm [notebook có output](notebooks/), [ảnh bằng chứng](screenshots/), [giải thích](EXPLANATIONS.md), [reflection](REFLECTION.md) và [khai AI](AI_USAGE.md). Các ảnh là screenshot trang output xuất từ ipynb, có ghi trạng thái thực thi.

Pytest ngày 04/10/2026: 20 PASS, 4 deselected; smoke gốc 8/9, runner gốc chưa có kết quả 8/8. Bài có 14 ảnh bằng chứng, thông tin người học đã xác nhận. Cần hoàn tất kiểm tra tổng hợp trước khi gửi PR. Chưa có commit SHA hoặc liên kết PR của bài nộp.

Xem [trạng thái](RUN_STATUS.md), [review đích cụ thể](REVIEW_20261004.json), [NB6 hoàn tất](logs/nb6_completed_20261004.json) và [kiểm tra kết quả deletion](logs/row_deletions_20261004.json). Chỉ xử lý file/snapshot NB6 đã được xác nhận; không dùng quarantine hoặc dry-run làm bằng chứng VACUUM thật.
