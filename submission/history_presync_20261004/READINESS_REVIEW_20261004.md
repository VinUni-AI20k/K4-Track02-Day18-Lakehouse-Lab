# Kiểm định trước khi nộp — 04/10/2026

**Kết luận: CHƯA SẴN SÀNG NỘP.** Bằng chứng nội dung NB1–NB8 đáp ứng các ngưỡng Part A/B; kiểm tra tổng hợp, trình tự chạy notebook và hồ sơ nộp còn việc phải hoàn tất. Đây là kiểm định bằng chứng, không phải điểm chấm chính thức.

Đối chiếu [README](../README.md), [rubric](../docs/RUBRIC.md), [submission](../docs/SUBMISSION.md), [checkpoints](../docs/CHECKPOINTS.md) và [rules](../docs/RULES.md). Đọc notebook/output/log/ảnh, kiểm tra Git và fork GitHub; chạy kiểm tra dữ liệu chỉ đọc bằng [audit_all_requirements.py](../scripts/audit_all_requirements.py) và [verify_remaining_readonly.py](../scripts/verify_remaining_readonly.py). Không reset bảng, xóa thêm dữ liệu hoặc chạy lại các test phá hủy trong lần kiểm định này.

## 1. Từng tiêu chí rubric bắt buộc

“Có bằng chứng” nghĩa là số đo và giải thích hiện có hỗ trợ tiêu chí; không bảo đảm điểm tối đa, vì người chấm còn xét hiểu biết và chất lượng giải thích.

| Tiêu chí | Điểm | Bằng chứng kiểm định | Kết luận |
|---|---:|---|---|
| NB1 tạo Delta và JSON log | 4 | 4 hàng, 2 JSON commits; ảnh có log và nội dung commit | Có bằng chứng |
| NB1 schema enforcement | 2 | Output lỗi cast `thirty` sang Int64; không dựa vào flag hardcoded | Có bằng chứng |
| NB1 schema evolution | 2 | Cột tier, 3 NULL và 1 premium | Có bằng chứng |
| NB2 ≥100 file trước optimize | 3 | 200 file ban đầu | Có bằng chứng |
| NB2 speedup ≥3× hoặc pruning ≥10× | 6 | Median 492,3→34,2 ms: 14,4×; 1/55 file: 55× pruning | Có bằng chứng |
| NB2 giảm file | 3 | 200→55 | Có bằng chứng |
| NB3 ≥5 versions gồm RESTORE | 4 | Live history v0–v4, RESTORE tại v4 | Có bằng chứng |
| NB3 MERGE 100K | 4 | 50K update + 50K insert | Có bằng chứng |
| NB3 RESTORE bỏ score âm | 4 | Live count score<0 = 0 | Có bằng chứng |
| NB4 đủ Bronze/Silver/Gold | 4 | 3 bảng đọc được | Có bằng chứng |
| NB4 dedup | 4 | 200.000→190.052 hàng; request_id Silver duy nhất | Có bằng chứng |
| NB4 Gold ≥7 dates×3 models, đúng metrics | 4 | 24 hàng = 8 dates×3 models; tính lại toàn bộ metrics khớp, sai số ≤1e-8 | Có bằng chứng |
| NB5 catalog và day(ts) | 3 | Output tạo qua SQLite catalog, partition transform day(ts) | Có bằng chứng |
| NB5 pruning ≥5× trên ts | 5 | Baseline 10→1 file; live sau evolution 13→1 | Có bằng chứng |
| NB5 metadata tree và byte ratio | 1 | 3 tầng metadata; 136,2 KB/47,3 KB ≈288% | Có bằng chứng |
| NB5 field ID và partition evolution | 4 | ID 4 giữ sau rename; spec 1 và 2 cùng tồn tại; live 5.500 hàng | Có bằng chứng |
| NB6 compaction ≥10× | 4 | 200→11 file: 18,18× | Có bằng chứng |
| NB6 clustering skip ≥50% | 3 | Min/max chọn 1/10 file, skip 90% | Có bằng chứng |
| NB6 VACUUM thu byte và Iceberg 3 snapshots | 3 | Xóa 211 file/16.907.742 byte; thu hồi ròng 16.907.155 byte; live 3 snapshots | Có bằng chứng |
| NB6 xử lý 3 orphan và manifest lists | 2 | 3 orphan/21.702 byte; 17 lists/37.907 byte đã xóa, kiểm tra vắng mặt | Có bằng chứng |
| NB6 checkpoint | 1 | Checkpoint tự động v99/v199 và _last_checkpoint tồn tại; không tạo lại thủ công | Có bằng chứng |
| NB7 amplification ≥5× | 4 | 200× theo độ hạt row group, có giải thích giới hạn phép đo | Có bằng chứng |
| NB7 int8 ≥3×, recall ≥.80, fidelity ≥.95 | 4 | 5,8×; recall .904; fidelity 1.000 | Có bằng chứng |
| NB7 semantic SQL đúng chủ đề | 1 | Query storage trả neighbours storage | Có bằng chứng |
| NB7 lifecycle 0/>0 | 4 | 0 hits trong bảng/8 hits index cũ; 8 CDF delete events | Có bằng chứng |
| NB8 trajectory, Silver partitions, Gold policies | 3 | 2 agent_version partitions, 2 policies | Có bằng chứng |
| NB8 pin version và replay | 3 | Pinned v0 1.578 steps; current v1 1.978; replay khớp count | Có bằng chứng |
| NB8 MCP offline simulation | 3 | 5 list_tables→1 catalog read; input_required; poll completed | Có bằng chứng |
| NB8 provenance | 2 | Đủ 4 bucket minh họa; 1.666/2.000 trainable, loại 334 UNCLASSIFIED | Có bằng chứng |
| Pytest gốc 24 test xanh | 2 | 20 PASS, 4 deselected | **Chưa đủ** |
| Runner gốc 8 notebook xanh từ clean setup | 4 | Chưa có log runner 8/8 từ clean setup | **Chưa đủ** |

Part A/B gồm các tiêu chí trị giá 94 điểm có bằng chứng; Part C 6 điểm chưa được chứng minh. Không quy đổi thành điểm dự kiến hoặc khẳng định 94/100.

## 2. Checkpoints và kiểm tra tổng hợp

- NB6: 9 assertion gốc PASS; Delta 100.000 hàng, Iceberg 2.000 hàng; hash 10 file Delta current không đổi. Đã kiểm tra 231 file được duyệt không còn tồn tại (211 VACUUM + 3 orphan + 17 lists). Expiry metadata-only: avro 40→40, sau sweep 40→23.
- NB7: 7 assertion gốc PASS; live user_042 = 0 trong docs_intable, v0 vẫn có 8. Log CDF có đúng 8 delete events.
- NB8: 10 assertion gốc PASS; live user_007 = 0, v0 vẫn có 8. Xóa subject là checkpoint/assertion, không có dòng điểm riêng trong rubric.
- Smoke gốc: **8/9**, chưa có lần chạy đầy đủ 9/9. CDF của NB7 không thay thế kết quả smoke gốc.
- Pytest gốc: **20/24**, không coi 4 deselected là PASS. Thiếu `test_cdf_emits_delete_events`, `test_expire_snapshots_is_metadata_only`, `test_catalogs_are_isolated_per_name`, `test_reset_catalog_does_not_touch_siblings`.
- Runner gốc: chưa có **8/8**. Các assertion riêng đã PASS không thay thế clean runner.
- Các notebook có output, không còn code cell thiếu execution_count/error output. Tuy nhiên NB6 có execution_count không tăng theo thứ tự do resume và thêm helper. Chưa chứng minh một lượt chạy từ đầu đến cuối theo mục 3 SUBMISSION.md; không sửa số đếm để giả lập lượt chạy đó.

Các kiểm tra còn thiếu có fixture/reset/expiry/delete ngoài danh sách NB6 đã được duyệt. Không tự mở rộng xác nhận cũ để chạy chúng trên dữ liệu hiện tại. Khi hoàn tất, cần dùng môi trường thử nghiệm riêng trong workspace, kiểm tra chính xác phạm vi thao tác và giữ nguyên bằng chứng hiện có.

## 3. Hồ sơ và quy trình nộp

| Yêu cầu | Hiện trạng |
|---|---|
| Fork cá nhân, tên đúng, origin đúng | Đạt; GitHub xác nhận fork DngVinh và parent VinUni-AI20k |
| INFO: họ tên/MSSV/mã bài/Python/OS/đường chạy | Đạt; Dương Xuân Vinh, 2A202602622 đã được xác nhận |
| Đủ 8 ipynb, output và giải thích | Có đủ; còn lưu ý lượt chạy NB6 như trên |
| ≥1 ảnh mỗi notebook, kết quả chính | 14 PNG hợp lệ, phủ đủ 8 NB; dùng ảnh completed mới cho NB6–8 |
| Câu hỏi 3.1–3.8 và khai AI | Có; phạm vi AI được khai |
| Reflection ≤200 từ | Đã sửa câu trạng thái cũ sau kiểm định; hiện 181 từ, khai AI giữ nguyên |
| Hồ sơ nhất quán | RUN_STATUS có các đoạn lịch sử 10/13/14 ảnh và trạng thái cũ; nên ghi rõ lịch sử hoặc tổng hợp lại trạng thái cuối |
| Không commit venv/lakehouse/cache/secrets | venv/lakehouse đang ignore; kiểm tra mẫu credentials không thấy; phải kiểm tra lại danh sách staged trước commit, không coi scan là bảo đảm tuyệt đối |
| Commit/push bài nộp | **Chưa**; submission/ và scripts hỗ trợ vẫn untracked |
| Kiểm tra bản nộp trên GitHub | API contents/submission trên default main trả 404; **chưa có thư mục nộp trên main** |
| PR, SHA bản nộp, gửi kênh lớp | Có PR_DRAFT cục bộ; chưa có bằng chứng bản nộp đã gửi. SHA commit cũ không phải SHA bài nộp |
| Deadline và trách nhiệm cá nhân | Phải theo ngày/kênh coach; chưa xác minh được. Người học cần đọc, hiểu và chịu trách nhiệm bài cá nhân |
| Bonus | Tùy chọn; không phải việc bắt buộc còn thiếu |

Ảnh là ảnh trang HTML xuất từ output notebook, đã khai rõ, không phải ảnh giao diện Jupyter. Notebook/log/ảnh cũ được giữ như lịch sử; không dùng ảnh chưa hoàn tất làm bằng chứng trạng thái cuối.

## 4. Việc còn lại trước khi chốt

1. Hoàn tất smoke gốc 9/9, pytest gốc 24/24, runner gốc 8/8 từ clean setup trong phạm vi dữ liệu thử nghiệm được phép; lưu log thật, không bỏ assertion/test để báo PASS.
2. Lưu bằng chứng notebook chạy từ đầu đến cuối theo hướng dẫn, đặc biệt NB6; không ghi đè bản lịch sử để che lần chạy cũ.
3. Reflection đã sửa; cần đồng bộ trạng thái cuối/khai AI/PR draft sau kết quả kiểm tra tổng hợp.
4. Review đúng tập file nộp, commit/push, xác minh notebook/output/ảnh trên GitHub, mở PR upstream.
5. Gửi link repo + link PR + SHA của commit đã nộp qua kênh lớp theo thông báo coach.

Bằng chứng chính: [EXPLANATIONS](EXPLANATIONS.md), [NB6 hoàn tất](logs/nb6_completed_20261004.json), [row deletions](logs/row_deletions_20261004.json), [audit NB6](logs/final_audit_nb6_20261004.json), [pytest 20 test](logs/pytest_safe_20261004.xml), [RUN_STATUS](RUN_STATUS.md).

Đã chuẩn bị môi trường mới với 412 file dữ liệu giả và kiểm tra hash/source/phạm vi thành công. Bộ kiểm tra đầy đủ và lượt chạy Jupyter đã có script thực thi, chờ ngoại lệ đúng phạm vi theo [VALIDATION_APPROVAL_20261004.md](VALIDATION_APPROVAL_20261004.md). Chưa ghi bất kỳ kết quả 9/9, 24/24 hoặc 8/8 nào khi chưa chạy.
