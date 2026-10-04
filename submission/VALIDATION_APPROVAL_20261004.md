# Review kiểm tra tổng hợp trong môi trường riêng

Đã chuẩn bị **412 file dữ liệu giả mới**, bằng đúng generators của repo, cho hai lượt chạy độc lập. Bài làm cũ, notebook/log/ảnh cũ và các bảng `_lakehouse/bronze`, `silver`, `gold`, `scratch`, `iceberg` được giữ nguyên. Chưa chạy thao tác phá hủy trong môi trường mới.

Danh sách canonical path, SHA256, số byte và trạng thái từng file: [VALIDATION_REVIEW_20261004.json](VALIDATION_REVIEW_20261004.json).

SHA256 của review: `39d944a5dcbc2db82598a13bdc96e615cd599f302fe5621718fbcb0e7a937f38`.

## Chính xác bốn thư mục dữ liệu thử nghiệm

| Canonical target | Thao tác cần cho kiểm tra gốc |
|---|---|
| `C:\Users\Duong Vinh\K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab\_lakehouse\validation_ready_20261004\smoke` | Smoke 9/9: delete id<5; reset catalog smoke; xóa hai bảng smoke sau test |
| `C:\Users\Duong Vinh\K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab\_lakehouse\validation_ready_20261004\pytest` | Pytest đủ 24 tests: delete id<3, expiry còn 2 snapshots, reset catalog nb6/drop, fixture mới và cleanup của pytest |
| `C:\Users\Duong Vinh\K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab\_lakehouse\validation_ready_20261004\runner` | Runner gốc 8/8: reset bảng/catalog nếu có; NB6 VACUUM/orphan/expiry/sweep/checkpoint; NB7/NB8 xóa subject giả |
| `C:\Users\Duong Vinh\K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab\_lakehouse\validation_ready_20261004\notebooks` | Chạy tuần tự 8 notebook trong kernel Jupyter của .venv; cùng thao tác lab như runner; lưu output mới riêng |

Các thư mục này chưa từng chứa dữ liệu người dùng. `pytest` chưa tồn tại để tránh pytest xóa basetemp cũ. Ba thư mục còn lại chỉ chứa dữ liệu mới vừa sinh. Các file đều untracked/ignored. Snapshot ID/tên file mới sẽ được thư viện sinh khi chạy; xin ngoại lệ theo đúng bốn thư mục trên, chỉ cho dữ liệu giả mới của lần kiểm tra này, không mở rộng sang nơi khác.

Tác động không phục hồi trực tiếp: VACUUM/orphan/sweep/cleanup xóa vật lý file thử nghiệm; expiry bỏ snapshot thử nghiệm. Có thể sinh lại fixture bằng generators, không khôi phục được tên file/ID ngẫu nhiên cũ. Phương án không xóa là giữ các log kiểm tra riêng hiện có; phương án đó không chứng minh đủ rubric reproducibility.

## Tại sao cần xác nhận mới

Nguồn: **AGENTS.md instructions do người dùng cung cấp trong hội thoại**, không có file AGENTS.md tại repo. Quy định ghi: “Permanent deletion of untracked or dirty data remains prohibited” và xác nhận phải “name the exact target or explicitly accept the displayed target list”. Quy định cũng yêu cầu người dùng trực tiếp yêu cầu thay đổi đúng protection trước khi có ngoại lệ.

Xác nhận cũ chỉ cho danh sách REVIEW_20261004.json của NB6; bốn môi trường mới không thuộc danh sách đó. Vì vậy cần xác nhận ngoại lệ riêng trước khi chạy bộ kiểm tra gốc, dù dữ liệu vừa được sinh để thử nghiệm.

Có thể trả lời nguyên câu:

> TÔI XÁC NHẬN THAO TÁC PHÁ HỦY NÀY: chấp nhận VALIDATION_REVIEW_20261004.json có SHA256 39d944a5dcbc2db82598a13bdc96e615cd599f302fe5621718fbcb0e7a937f38; xác nhận dữ liệu trong bốn thư mục smoke, pytest, runner, notebooks dưới _lakehouse/validation_ready_20261004 là dữ liệu giả dùng một lần. Thay đổi lệnh cấm xóa ignored/untracked và thao tác đệ quy chỉ cho bốn thư mục này: cho phép reset, cleanup, VACUUM, xóa orphan/manifest lists, expiry snapshots, xóa dòng và ghi đè metadata sinh ra, kể cả file giả được tạo trong lần kiểm tra này. Giữ nguyên mọi dữ liệu và bằng chứng hiện có ngoài bốn thư mục này.

Sau xác nhận, [complete_submission_validation.py](../scripts/complete_submission_validation.py) kiểm tra lại hash và tập file, chạy smoke/pytest/runner gốc không deselect test hoặc sửa assertion, rồi chạy 8 notebook tuần tự bằng Jupyter. Output mới lưu tại `submission/validation_20261004/`; bản nộp chính chỉ cập nhật sau khi kiểm tra kết quả và giữ bản trước đó.
