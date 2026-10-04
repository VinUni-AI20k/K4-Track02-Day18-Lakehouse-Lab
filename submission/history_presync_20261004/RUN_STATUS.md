# Trạng thái thực thi

**Cả 8 notebook đã có output hoàn tất.** NB6/NB7/NB8 giữ nguyên assertion cuối và PASS. Audit dữ liệu: [final_audit_nb6_20261004.json](logs/final_audit_nb6_20261004.json). Bài chưa sẵn sàng nộp: kiểm tra tổng hợp còn thiếu, NB6 chưa có lượt chạy liền từ đầu đến cuối và bài chưa commit/push/PR. Đối chiếu đầy đủ: [READINESS_REVIEW_20261004.md](READINESS_REVIEW_20261004.md). Các đoạn bên dưới ghi lịch sử các lần chạy; ảnh và log cũ được giữ nguyên, không đại diện trạng thái cuối.

| Notebook | Trạng thái |
|---|---|
| 01_delta_basics | complete |
| 02_optimize_zorder | complete |
| 03_time_travel | complete |
| 04_medallion | complete |
| 05_iceberg_catalog | complete |
| 06_maintenance | complete (9 assertion gốc PASS ngày 04/10/2026) |
| 07_vectors_multimodal | complete (assertion gốc PASS ngày 04/10/2026) |
| 08_agents_provenance | complete (assertion gốc PASS ngày 04/10/2026) |

20 pytest PASS; 4 test chưa chạy vì có delete, expiry hoặc reset catalog. Smoke gốc giữ kết quả 8/9; CDF đã được chứng minh trong NB7 nhưng chưa chạy lại toàn bộ smoke gốc. Chưa đạt yêu cầu full pytest và run-all. Xác nhận mới chỉ cho phép các đích NB6 trong REVIEW_20261004.json, không mở rộng sang fixture/reset/cleanup của bộ kiểm tra tổng hợp.

[Danh sách cũ](DESTRUCTIVE_REVIEW.json) được giữ để đối chiếu. [Danh sách ngày 04/10/2026](REVIEW_20261004.json) ghi các đích đã duyệt. Người học đã xác nhận riêng `row_deletions`, sau đó thay đổi lệnh cấm xóa ignored/untracked chỉ cho 211 file VACUUM, 3 orphan, 17 snapshot IDs và 17 manifest lists của NB6. Đã kiểm tra lại version/hash/tập đích trước thao tác và hoàn tất đúng phạm vi. Các files đã xóa không còn phục hồi bằng phương án quarantine trong bản review ban đầu.

**NB6 hoàn tất:** VACUUM xóa 211 file / **16.907.742 byte**, thu hồi ròng **16.907.155 byte** sau khi tính 587 byte log mới. Xử lý 3 orphan / **21.702 byte**. Iceberg **20 → 3 snapshots**, avro **40 → 40** sau expiry rồi **40 → 23** sau sweep; 17 manifest lists / **37.907 byte** đã xóa. Delta giữ **100.000 hàng**, Iceberg giữ **2.000 hàng**, hash 10 file Delta current không đổi. Cả 9 assertion gốc PASS. Log: [nb6_completed_20261004.json](logs/nb6_completed_20261004.json); ảnh: [nb06_completed_20261004.png](screenshots/nb06_completed_20261004.png). Tổng cộng **14 PNG**; notebook/log/ảnh trước đó đều được giữ.

Baseline trước khi được phép xử lý lưu trong [preparation_20261004.json](logs/preparation_20261004.json): Iceberg 20 snapshots/2.000 hàng, CDF 2.000 hàng, 3 orphan/21.702 byte, VACUUM 211 ứng viên/16.907.742 byte. Đây là trạng thái trước thao tác, không phải trạng thái hiện tại.

Đã sửa hai lỗi đường dẫn trong source NB6: ghép tên file VACUUM tương đối với table path để đo byte, và giải mã `%20` của `file_uris()` trước khi so với đường dẫn trên đĩa. Không thay output cũ 0 B thành output giả. Lần chạy chuẩn bị đầu dừng ở kiểm tra URI trước khi ghi dữ liệu; sau khi sửa đã chạy thành công.

Chạy lại pytest ngày 04/10/2026: **20 PASS, 4 deselected** trong 3,56 giây, giữ toàn bộ dữ liệu test. Log mới: [pytest_safe_20261004.xml](logs/pytest_safe_20261004.xml). Không coi đây là 24/24. Họ tên và MSSV trong INFO.md đã được người học xác nhận.

NB7: `user_042` có **0 hits trong bảng, 8 hits ở index cũ**, CDF phát ra đúng **8 delete events**. Cả 7 assertion gốc PASS. NB8: `user_007` có **8 → 0 hàng**, version **0 → 1**, cả 10 assertion gốc PASS. Ba bảng vẫn đọc được **2.000 hàng ở v0**; current có **1.992 hàng**. Bằng chứng kiểm tra độc lập: [row_deletions_20261004.json](logs/row_deletions_20261004.json). Lệnh resume hoàn tất deletion/assertion nhưng audit cuối gặp lỗi Arrow string/string_view; phục hồi bằng bước chỉ đọc toàn bảng, không chạy lại lệnh delete.

Notebook chính đã nhận output mới bằng patch, bản gốc giữ trong `history_20261004/`, bản sau resume giữ trong `revisions_20261004/`. Ảnh mới: [NB7 hoàn tất](screenshots/nb07_completed_20261004.png), [NB8 hoàn tất](screenshots/nb08_completed_20261004.png), [NB6 baseline](screenshots/nb06_preparation_20261004.png). Tổng cộng **13 PNG**. Các ảnh/HTML cũ được giữ như bằng chứng lần chạy trước. Lần render mới đầu thất bại do Chrome GPU trong sandbox; lần thử lại với quyền thực thi đã thành công, không tắt sandbox của Chrome.

Notebook có output, Markdown giải thích và trả lời câu hỏi thử thách. Xem [EXPLANATIONS.md](EXPLANATIONS.md).

Đã xuất tám trang bằng chứng HTML và chụp thành công tám ảnh PNG chính cùng hai ảnh bổ sung (version pin và VACUUM dry-run), tổng cộng 10 ảnh trong `submission/screenshots/`. Đây là ảnh các trang bằng chứng xuất từ ipynb, không phải giao diện Jupyter. Ảnh NB6–NB8 ghi rõ chưa hoàn tất. Các lần chụp ban đầu thất bại; lần chạy sau thành công, giữ nguyên artifacts trước đó.

Đã có [REFLECTION.md](REFLECTION.md), 183 từ tính cả tiêu đề/link, kèm khai phạm vi AI. Người học cần kiểm tra và chịu trách nhiệm về nội dung trước khi nộp.

GitHub CLI xác nhận `origin` là fork `DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab`, parent `VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab`, default branch `main`. `.venv/` và `_lakehouse/` được Git ignore. Chưa commit, push hoặc tạo PR vì chưa đáp ứng điều kiện hoàn tất notebook/kiểm tra tổng hợp.

Audit [submission_audit.json](logs/submission_audit.json) xác nhận đủ 8 notebook có cell giải thích, không có error output, 10 PNG hợp lệ và reflection trong giới hạn. `ready_to_submit=false` vì các notebook và kiểm tra tổng hợp còn thiếu. Có [bản nháp PR](PR_DRAFT.md), chưa gửi.

Kiểm tra bổ sung chỉ đọc trong [additional_checks.json](logs/additional_checks.json) xác nhận điều kiện Gold, uniqueness của Silver và notebook không có error output. Checkpoint tự động đã tồn tại ở v99/v199; cell checkpoint thủ công của NB6 chưa thực thi.
