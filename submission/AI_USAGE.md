# Phạm vi hỗ trợ AI

Codex thực hiện đồng bộ gói nộp, bảo toàn bản cũ, cập nhật báo cáo và chuẩn bị commit/push/PR theo yêu cầu người học. Bộ kiểm tra gốc và Jupyter tuần tự đã PASS đầy đủ trong môi trường riêng; không thay assertion, không giả output. Người học chịu trách nhiệm đọc, hiểu và khai báo hỗ trợ AI.

**Trạng thái cuối ngày 04/10/2026: phần kỹ thuật và gói notebook đã hoàn tất.** Smoke **9/9**, pytest **24/24** (không deselect), runner **8/8**, Jupyter tuần tự **8/8** đều PASS. [Kết quả](validation_20261004/results.json), [smoke](validation_20261004/smoke_full.txt), [pytest](validation_20261004/pytest_full.xml), [runner](validation_20261004/runner_full.txt), [Jupyter](validation_20261004/jupyter_sequential.txt).

Tám notebook trong `notebooks/` đã nhận code/output tuần tự thật và giữ giải thích/câu trả lời với nhãn lịch sử. Bản trước đồng bộ giữ nguyên tại `history_presync_20261004/`; bản Jupyter gốc tại `validation_20261004/notebooks/`. 14 PNG cùng log/HTML cũ được giữ như bằng chứng các lần đo trước. [Kiểm tra bảo toàn](validation_20261004/preservation_verified.json) xác nhận 2.838 file có hash không đổi trong lượt validation. Không còn kiểm tra kỹ thuật thiếu.

Đã commit/push lên [fork cá nhân](https://github.com/DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab) và mở [PR #8](https://github.com/VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab/pull/8) về `VinUni-AI20k:main` (OPEN, không draft). Đã đối chiếu hash file trên GitHub với commit cục bộ: đủ 8 notebook chính và 14 PNG. SHA bản nộp cuối là head commit của PR, được cung cấp khi bàn giao. **Chưa gửi kênh lớp:** đang chờ nền tảng/tên kênh hoặc đường dẫn cụ thể từ người học.

## Lịch sử hỗ trợ trước khi chốt

Codex cài dependencies, sinh dữ liệu giả, thực thi code notebook trên máy này bằng IPython, lưu output thật và viết bản giải thích dựa trên output. Người học cần mở notebook, kiểm tra từng bước, tự giải thích và khai báo hỗ trợ này khi nộp. Không giả số liệu, không bỏ assertion hoặc hạ ngưỡng.

Lịch sử lần chạy ban đầu: runner chỉ chấp nhận reset khi đích chưa tồn tại, dừng trước VACUUM thật và delete. Sau xác nhận riêng cho ba predicate, NB7/NB8 đã tiếp tục và PASS assertion gốc; lúc đó NB6 chưa hoàn tất. Smoke gốc chỉ chạy 8/9 checks và giữ artifacts; pytest chạy 20/24 tests, loại 4 test phá hủy khỏi lần chạy này. Các phần chưa chạy không được coi là PASS.

Cập nhật cuối NB6: sau xác nhận trực tiếp thay đổi lệnh cấm chỉ cho đúng đích REVIEW_20261004.json, Codex kiểm tra lại version/hash, chạy VACUUM thật, xử lý 3 orphan, expiry 17 snapshot IDs và sweep 17 manifest lists. Giữ 100.000 hàng Delta, 2.000 hàng Iceberg và hash file current; 9 assertion gốc PASS. Cập nhật notebook bằng patch, giữ bản trước thao tác trong history_nb6_20261004/, thêm log/ảnh mới. Cả 8 notebook có output hoàn tất; tổng 14 PNG. Các đoạn nói NB6 chưa hoàn tất bên dưới là lịch sử trước xác nhận. Chưa chạy đầy đủ smoke/pytest/runner hoặc commit/push/PR.

Codex bổ sung trả lời câu hỏi thử thách 3.1–3.8 trong notebook và EXPLANATIONS.md, xuất HTML từ output thật và chụp PNG các trang này bằng Chrome headless. Ảnh ghi rõ nguồn ipynb và trạng thái thực thi; không tạo output giả. Các lần chụp đầu thất bại, lần sau thành công. Codex soạn reflection dựa trên observability và số đo NB2; người học cần kiểm tra, hiểu và xác nhận nội dung trước khi nộp.

Ngày 04/10/2026, Codex sửa cách đo byte VACUUM và xử lý đường dẫn URI có dấu cách trong source NB6; tạo bổ sung 3 orphan, baseline Iceberg 20 snapshots và bảng CDF mà không reset/xóa dữ liệu. Codex đo và lập manifest SHA256 để kiểm tra các đích đề xuất, chạy lại 20 test an toàn (4 test phá hủy không chạy), cập nhật thông tin người học theo xác nhận trực tiếp. Baseline và dry-run không được ghi thành kết quả deletion, expiry hoặc VACUUM đã hoàn tất. Output notebook và ảnh cũ được bảo toàn.

Sau câu xác nhận trực tiếp, Codex xóa đúng các dòng trong `row_deletions` đã duyệt, giữ nguyên các file/version cũ, tiếp tục notebook bằng dữ liệu hiện có và chạy các assertion gốc. NB7 có 0 hits in-table, 8 hits external và 8 CDF delete events; NB8 có user_007 từ 8 xuống 0. Ba bảng v0 vẫn đọc đủ 2.000 hàng. Notebook được cập nhật bằng patch và có bản sao trước/sau; thêm 3 PNG bằng chứng thật (tổng 13), cập nhật giải thích/trạng thái/bản nháp PR. Audit cuối gặp khác biệt kiểu Arrow, được khắc phục bằng kiểm tra chỉ đọc, không lặp lại delete. Không chạy VACUUM, expiry, sweep, reset catalog, commit/push hay gửi PR.
