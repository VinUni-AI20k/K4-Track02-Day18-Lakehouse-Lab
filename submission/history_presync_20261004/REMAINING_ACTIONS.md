# Những việc còn chặn nộp sau ngày 04/10/2026

Cả 8 notebook có output hoàn tất. NB6/NB7/NB8 đã chạy nguyên assertion cuối, không hạ ngưỡng. Xem [audit mới nhất](logs/final_audit_nb6_20261004.json) và [trạng thái](RUN_STATUS.md).

## NB6 đã hoàn tất

- Sau xác nhận đúng phạm vi, VACUUM thật xóa 211 file; thu hồi ròng 16.907.155 byte.
- Đã xử lý 3 orphan / 21.702 byte; Iceberg expiry 20 → 3 snapshots và sweep 17 manifest lists / 37.907 byte.
- Delta vẫn có 100.000 hàng, Iceberg 2.000 hàng; hash 10 file Delta current không đổi. Checkpoint tự động v99/v199 và `_last_checkpoint` được giữ và kiểm tra.
- Cả 9 assertion gốc PASS. Log: [nb6_completed_20261004.json](logs/nb6_completed_20261004.json); ảnh mới: [nb06_completed_20261004.png](screenshots/nb06_completed_20261004.png). Bản notebook trước thao tác giữ trong history_nb6_20261004/.

Danh sách đích: [REVIEW_20261004.json](REVIEW_20261004.json). Row_deletions và các đích NB6 đã được xác nhận, thực thi. Ngoại lệ xóa file chỉ áp dụng đúng dữ liệu giả NB6 trong danh sách; chưa bao gồm bất kỳ fixture/reset/cleanup nào của bộ kiểm tra tổng hợp.

## Kiểm tra tổng hợp và nộp

Đã sửa reflection còn 181 từ và làm rõ lịch sử trong RUN_STATUS/AI_USAGE. Đã chuẩn bị 412 file dữ liệu giả riêng, giữ nguyên các bảng/bằng chứng cũ. Script và đích review sẵn sàng trong [VALIDATION_APPROVAL_20261004.md](VALIDATION_APPROVAL_20261004.md); chỉ chờ xác nhận ngoại lệ cho đúng bốn thư mục mới trước khi chạy test gốc và Jupyter tuần tự.

- Pytest: 20 PASS, 4 deselected. Bốn test còn lại là CDF delete, snapshot expiry và hai reset catalog; không được ghi thành 24/24.
- Smoke gốc: 8/9 theo log trước. NB7 đã chứng minh CDF delete, nhưng đó không phải lần chạy đầy đủ smoke gốc 9/9. Smoke gốc còn cleanup/reset dữ liệu.
- Runner gốc chưa có 8/8; chạy trực tiếp sẽ reset bảng/catalog hiện có và xóa file. Cần kiểm tra các tác động này trước khi người học chạy trong môi trường thử nghiệm tách biệt.
- Sau khi kiểm tra tổng hợp hoàn tất, cập nhật trạng thái và bản nháp PR theo kết quả cuối. Sau đó commit/push, kiểm tra GitHub, mở PR về repo đề bài và gửi repo URL + PR URL + commit SHA qua kênh lớp. Chưa gửi bất kỳ nội dung nào qua kênh lớp.

Ảnh mới ngày 04/10/2026 nằm trong screenshots/ với hậu tố 20261004; các ảnh và logs cũ vẫn giữ để đối chiếu. INFO.md đã được người học xác nhận. Bonus tùy chọn, không phải blocker.
