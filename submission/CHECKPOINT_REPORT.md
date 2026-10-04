# Báo cáo checkpoint - Đỗ Quốc An / 2A202602892

Lần thực thi: 2026-10-04T19:34:23.499092+07:00 (UTC+7). Số liệu lấy từ output Jupyter; [metrics.json](evidence/metrics.json) chứa bản máy đọc được. Đường lightweight, không suy ra Spark đã chạy. Việc chấm điểm do coach quyết định.

| Checkpoint | Kết quả thực tế | Bằng chứng |
|---|---|---|
| 0 | Smoke 9/9 PASS; Python 3.11; origin có tài khoản/tên repo đúng mẫu | [smoke](logs/smoke.txt), [environment](evidence/environment.json) |
| 1 | 2 commits; bad age bị chặn; 4 rows sau merge schema; tier premium=1, NULL=3 | [NB1](notebooks/01_delta_basics.ipynb), [ảnh](screenshots/nb01_delta_basics.png) |
| 2 | 200 -> 55 active files; speedup 7.12x; pruning 55x, 1 file chứa target | [NB2](notebooks/02_optimize_zorder.ipynb), [ảnh](screenshots/nb02_optimize_zorder.png) |
| 3 | MERGE 100,000 source rows; current 150,000; 5 versions có RESTORE; score âm=0 | [NB3](notebooks/03_time_travel.ipynb), [ảnh](screenshots/nb03_time_travel.png) |
| 4 | Bronze 200,000 -> Silver 190,052; Gold 7 ngày UTC x 3 model = 21 rows; p50<=p95, cost>0, error_rate hợp lệ | [NB4](notebooks/04_medallion.ipynb), [ảnh](screenshots/nb04_medallion.png) |
| 5 | 10 -> 1 file khi lọc ts; pruning 10x; field ID=4; specs [1, 2]; 5,500 rows đọc được | [NB5](notebooks/05_iceberg_catalog.ipynb), [ảnh](screenshots/nb05_iceberg_catalog.png) |
| 6 | Compaction 200 -> 11 (18.18x); skip 90%; vacuum thu 16,906,419 bytes; 3 Delta orphan; Iceberg 20->3 snaps, sweep17 manifest lists; checkpoint có | [NB6](notebooks/06_maintenance.ipynb), [ảnh](screenshots/nb06_maintenance.png) |
| 7 | Amplification 200.05x; int8 nhỏ 5.80x; recall@10 0.904; topic fidelity 1.000; deleted hits table=0/index=8; CDF 8 deletes | [NB7](notebooks/07_vectors_multimodal.ipynb), [ảnh](screenshots/nb07_vectors_multimodal.png) |
| 8 | Pin v0: 1,578 steps, current 1,978; 2 policies; 5 list calls/1 read; input_required; task completed; 4 buckets + UNCLASSIFIED 334; subject8->0 | [NB8](notebooks/08_agents_provenance.ipynb), [ảnh](screenshots/nb08_agents_provenance.png) |
| 9 - phần local | 24/24 tests; 8/8 scripts; 8/8 Jupyter notebooks có output; 8 PNG; reflection 170 từ; INFO/AI usage/bonus đầy đủ | [pytest](logs/pytest.txt), [run-all](logs/run_all.txt), [audit](evidence/audit.json) |

## Giải thích số liệu

NB1 kiểm exception và tính nguyên vẹn sau bad write, không dùng PASS cố định. NB2 gom dữ liệu để min/max isolate user; tốc độ wall-clock có thể đổi theo cache/CPU, còn ngưỡng pruning 10x vẫn là lựa chọn rubric. NB3 RESTORE là commit mới, không xóa history.

NB4 loại 9,948 retry; đặt session DuckDB UTC để không biến 7 ngày nguồn thành 8 ngày địa phương. Giá token trong notebook là fixture. NB5 metadata:data = 290.3% trên toy table; lọc nguồn ts suy ra day(ts), rename giữ ID và spec evolution không rewrite hết dữ liệu.

NB6 file count là active file; bytes trên disk có tombstone cho tới vacuum. Với deltalake/PyIceberg trong requirements-lock, orphan chưa commit không có tombstone để vacuum biết; expiry giảm snapshot chưa dọn file, nên sweep riêng. Production sweep phải xét mọi snapshot còn giữ, reader/writer leases và age guard; scratch retention0 không phải khuyến nghị production.

Lưu ý output gốc NB6: dry-run báo0 B vì helper du nhận đường dẫn relative do vacuum trả về, chưa resolve từ table root; số bytes thu hồi trong báo cáo đo bằng chênh lệch toàn thư mục trước/sau vacuum, không dựa vào dự đoán0 B. Số Parquet trên disk sau orphan sweep gồm cả checkpoint trong _delta_log, nên có thể lớn hơn active data files; find_orphans đã loại _delta_log.

NB7 amplification là proxy từ row-group bytes chưa nén/one-blob, không phải traffic mạng đo được. Vector toy có cấu trúc topic, không phải embedding model thật. In-table delete không tự đồng bộ derived index; CDF ghi đủ8 sự kiện để consumer evict.

NB8 replay chỉ kiểm count, chưa so hash nội dung. MCP offline không server/authorization: cache list_tables, confirmed do caller cấp, delete_rows no-op. Mapping CC-BY->public_domain và consent->scraped_optout_checked là fixture hạn chế; không kết luận quyền sử dụng/tuân thủ pháp luật. Subject không còn trong version hiện tại nhưng version cũ còn dữ liệu.

## Phần còn phải làm để nộp

Các checkpoint kỹ thuật và bộ deliverable local đã được kiểm tra. Checkpoint0/9 về GitHub và nộp lớp chỉ hoàn tất khi bạn tự đọc/chạy theo RULES, xác nhận đây là fork cá nhân, commit/push, mở PR và gửi repo+PR+SHA qua kênh coach. Chưa có commit/PR nộp bài được tạo trong phiên này. Xem [HUONG_DAN_NOP_BAI.md](HUONG_DAN_NOP_BAI.md).

Bonus có 7 quyết định (mỗi quyết định loại 2 alternatives), diagram medallion, storage/compute math, 6 failure modes và MVP một tuần. Các sizing/price là giả định có nhãn; không tuyên bố đã benchmark production hay chạy PoC retention riêng.
