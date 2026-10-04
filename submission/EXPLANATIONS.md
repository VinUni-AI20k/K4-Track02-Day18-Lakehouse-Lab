# Giải thích kết quả theo thử thách 3.1–3.8

Bản hỗ trợ AI dựa trên output thực tế trong `submission/notebooks/`; người học cần kiểm tra và diễn đạt lại bằng hiểu biết của mình. Cả 8 notebook đã hoàn tất phần output/assertion. Smoke 9/9, pytest 24/24, runner 8/8 và Jupyter tuần tự 8/8 đã PASS. Các số đo chi tiết dưới đây thuộc lần đo trước, đối chiếu với lịch sử và ảnh; output tuần tự cuối trong notebook chính là nguồn số đo mới nhất.

## 3.1 — Schema và transaction log

Schema enforcement kiểm tra dữ liệu ghi theo schema hiện có. Output thực tế báo `Cannot cast string 'thirty' to value of Int64 type`, nên hàng sai kiểu không được ghi. Schema evolution thay đổi schema khi được cho phép: `schema_mode="merge"` thêm `tier`; ba hàng cũ có NULL, hàng mới có `premium`. Opt-in giúp người ghi chủ động chấp nhận thay đổi cấu trúc, tránh lỗi tên cột tự trở thành thay đổi schema.

Hai commit JSON cho biết schema/protocol, thao tác WRITE, số hàng, file Parquet được thêm và thống kê file. Chúng là bằng chứng commit được ghi nhận; không thay thế việc kiểm tra nội dung toàn bộ dữ liệu hay quyền truy cập. DuckDB trả `(premium, 1)` và `(NULL, 3)`. Cờ PASS enforcement cuối notebook là hardcoded; lỗi thật ở cell ghi sai mới là bằng chứng.

## 3.2 — Compaction, Z-order và phép đo

Compaction gộp các file nhỏ để giảm overhead mở file và planning. Z-order tổ chức dữ liệu theo `user_id` để khoảng min/max của mỗi file hẹp hơn, giúp bỏ qua file không chứa giá trị cần tìm. Nếu chỉ còn một file, engine không còn nhiều file để chọn bỏ qua; đó là lý do notebook giữ target 256 KiB.

Số đo: **200 → 55 file**, median **492,3 → 34,2 ms**, speedup **14,4×**. Sau Z-order chỉ **1/55 file** có khoảng chứa `user_id=4242`, pruning **55×**. Cả hai ngưỡng đều đạt. Thời gian khác giữa các máy vì tốc độ storage/CPU, cache, tải nền và scheduling. Median ba lần giảm tác động outlier nhưng chưa phải benchmark production.

## 3.3 — Đọc version cũ và RESTORE

Time travel đọc một snapshot cụ thể mà không thay đổi trạng thái hiện tại. RESTORE thay đổi trạng thái hiện tại bằng một commit mới tham chiếu các file của version được chọn. Giữ lịch sử giúp audit biết cả lần ghi sai lẫn lần khôi phục, đồng thời giữ các reader đã pin version.

MERGE 100K mất **0,14 s**: 50K update và 50K insert. RESTORE v2 mất **0,03 s**, tạo v4; history có **5 version**, số hàng `score<0` hiện tại bằng **0**. Bản v3 chứa dữ liệu lỗi vẫn còn đọc được vì chưa vacuum bảng này.

## 3.4 — Medallion cho observability

Dedup ở Silver ngăn retry cùng `request_id` bị đếm nhiều lần, làm sai số request, latency và chi phí. Bronze có **200.000** hàng; Silver có **190.052**, giảm **9.948 (4,974%)**. Query giữ bản có timestamp sớm nhất; lựa chọn này phù hợp fixture của lab, nhưng production cần quy tắc rõ cho retry có payload thay đổi.

Dashboard đọc Gold để truy vấn bảng tổng hợp nhỏ, thay vì lặp parse JSON, dedup và tính percentile trên toàn bộ Bronze. Gold có **24 hàng = 8 ngày × 3 model**. Kiểm tra bổ sung xác nhận từng ngày đủ ba model, `p50≤p95`, chi phí dương và error rate trong [0,1]. DuckDB dùng **Asia/Bangkok**, nên bảy ngày UTC trải qua tám ngày địa phương khi CAST sang DATE.

Error rate là tỷ lệ hàng Silver có `status<>'ok'`, gồm cả `rate_limited` và `error`. Chi phí là tổng input/output token nhân đơn giá riêng từng model, chia 1 triệu; đây là giá minh họa. Nó phù hợp các trường token trong fixture, nhưng việc dedup bỏ retry cũng bỏ chi phí retry nếu mỗi retry được nhà cung cấp tính phí riêng. Query hiện giả định JSON hợp lệ; chưa chứng minh xử lý malformed JSON dù comment có nhắc đến.

Ba bảng nằm ở `_lakehouse/bronze/llm_calls_raw`, `_lakehouse/silver/llm_calls` và `_lakehouse/gold/llm_daily_metrics`.

## 3.5 — Iceberg và catalog

Hidden partitioning lưu transform `day(ts)` trong metadata; planner suy ra partition phù hợp khi người dùng lọc trên `ts`. Số file full scan/one-day scan là **10/1**, pruning **10×**, trả 500 hàng. Đây là SQLite catalog và planning trên client, không phải server-side planning hoặc cơ chế phân quyền.

Metadata tree đi từ catalog tới metadata JSON, manifest list, manifests rồi data files. Tại bước đo, metadata **136,2 KB**, data **47,3 KB**: tỷ lệ metadata/data **288,0%**. Dòng gốc nói “of table size” nhưng mẫu số trong code thực chất là data bytes, không phải tổng metadata+data.

Field ID tách định danh cột khỏi tên: rename `latency_ms` thành `latency_millis` vẫn giữ **ID 4**, nên file cũ đọc đúng mà không rewrite. Partition evolution giữ spec ID trên mỗi file; engine đọc theo spec của file đó. Sau append, **spec 1 và 2** cùng tồn tại, đọc được **5.500 hàng**, không cần chuyển layout mọi file cũ ngay.

## 3.6 — Maintenance: kết quả đã đo

Đã đo **200 → 11 file (18,18×)** sau compaction, clustering chọn **1/10 file**, skip **90%**, current table vẫn có **100.000 hàng**. Rewrite tạo file mới và tombstone file cũ nên byte vật lý tăng trước khi thu hồi.

VACUUM thật xóa đúng **211 file / 16.907.742 byte**. Tổng dung lượng bảng giảm **23.887.810 → 6.980.655 byte**, thu hồi ròng **16.907.155 byte**; chênh 587 byte là log mới. Output 0 B trước đó xuất phát từ tên file tương đối, được giữ như bằng chứng lần chạy cũ. Checkpoint tự động v99/v199 và `_last_checkpoint` đã được kiểm tra, không ghi đè lại. Cả 9 assertion gốc NB6 PASS.

Theo thiết kế phép thử, orphan chưa từng commit không có tombstone trong Delta log; dry-run canary của phiên bản đã cài xác nhận vacuum không liệt kê orphan đó. Không nên dùng phép hiệu “file trên đĩa − file current” rồi xóa ngay: một file có thể còn thuộc version cũ hoặc writer chưa commit; cần kiểm tra retention và toàn bộ tham chiếu cần giữ.

Trong PyIceberg 0.12.0 đã đo: expiry **20 → 3 snapshots**, avro vẫn **40 → 40**, metadata tăng do ghi JSON mới. Sweep xóa đúng **17 manifest lists / 37.907 byte**, avro còn **23**, dữ liệu vẫn **2.000 hàng**. Delta sweep xóa 3 orphan / 21.702 byte; dữ liệu vẫn 100.000 hàng và hash file current không đổi. Snapshot expiry thay đổi tham chiếu; sweep xóa vật lý. Retention quá ngắn làm mất time travel hoặc phá reader cũ.

Hai điểm đọc output: `count_files()` tính cả 2 checkpoint Parquet trong `_delta_log`, nên 12 Parquet trên đĩa không có nghĩa còn 2 orphan data. Dry-run sau VACUUM vẫn liệt kê tombstone của 211 file đã xóa; đó không phải bằng chứng chúng vẫn tồn tại. Sự vắng mặt của đúng từng file đã duyệt và hash các file current được kiểm tra riêng. Không dùng phép trừ tổng Parquet hoặc danh sách dry-run thay cho kiểm tra tham chiếu/vật lý.

## 3.7 — Blob, vector và lifecycle

Blob inline có row group 200 hàng, khoảng 12,5 MB; pointer lấy một blob 64 KiB. Amplification theo độ hạt row group là **200×**; đây không phải đo trực tiếp traffic ổ đĩa. Projection không lấy cột blob thì vẫn đọc ít byte; tránh kết luận inline luôn tệ cho analytical scan.

float32 dùng 1.024 byte/vector 256 chiều; int8 dùng 256 byte. Trên đĩa, bảng int8 nhỏ **5,8×** vì compression và metadata khác nhau. Recall@10 **0,904** so ID hàng top-10 với float32; topic fidelity **1,000** đo tỷ lệ kết quả cùng chủ đề query. Hai chỉ số khác nhau: có thể đổi láng giềng ID nhưng vẫn giữ chủ đề. Kết quả chỉ áp dụng corpus giả được đo.

Delta đọc embedding về `list<float>` thay vì fixed-size list; query cast sang `FLOAT[256]` trước cosine similarity. SQL query chủ đề storage trả các hàng storage. Sau xóa đúng 8 dòng `user_042`, có **0 hits in-table và 8 hits external**, current giảm **2.000 → 1.992 hàng** nhưng index giữ 2.000 vector. CDF phát đúng **8 delete events**, mang doc_id cần loại khỏi index. Cả 7 assertion gốc PASS. External index cần nhận delete events và xử lý update/reprocessing để tránh embedding lỗi thời; bảng v0 vẫn chứa dữ liệu trước xóa vì chưa VACUUM.

## 3.8 — Version pin và provenance

Pin version xác định dữ liệu mà training run đã đọc, dù bảng tiếp tục nhận append. Run pin **v0/1.578 bước**; current v1 có **1.978 bước**, replay v0 vẫn **1.578**. Đó là kiểm tra row count, chưa chứng minh toàn bộ nội dung bằng nhau. Silver có hai partition policy, Gold có hai policy.

Mô phỏng gọi `list_tables` năm lượt với **một catalog read**, trả `input_required` trước destructive call và task poll tới `completed`. Production cần xác thực/ủy quyền độc lập, kiểm tra server-side, quản lý cache và task bền vững. Cờ `confirmed` do caller truyền không phải ranh giới an toàn; `delete_rows` trong mô phỏng là no-op, không phải xóa dữ liệu thật.

Corpus có bốn bucket minh họa và UNCLASSIFIED: tập trainable giữ **1.666/2.000**, loại **334**. CC BY 4.0 không đồng nghĩa public domain, và ownership+consent không chứng minh đã kiểm tra opt-out. Không dùng mapping này như chứng nhận quyền training hoặc pháp lý.

Đã xóa đúng **8 hàng user_007** sau xác nhận trực tiếp: **8 → 0 hàng**, Delta **v0 → v1**; cả 10 assertion gốc PASS. Bảng hiện tại có 1.992 hàng; v0 vẫn đọc đủ 2.000 hàng và chứa 8 hàng subject đó. Delete tạo version mới, không xóa file vật lý. Phép thử chứng minh current visibility, không chứng minh erasure khỏi mọi version, external index hay bản sao khác. Kết quả được kiểm tra độc lập trong [row_deletions_20261004.json](logs/row_deletions_20261004.json).

## Trạng thái nộp

Pytest gốc 24/24, smoke gốc 9/9, runner gốc 8/8 và Jupyter tuần tự 8/8 đều PASS; xem validation_20261004/results.json và các log cùng thư mục. NB6/NB7/NB8 PASS assertion gốc; cả 8 notebook có output hoàn tất. Gói notebook đã đồng bộ output tuần tự và giữ giải thích/lịch sử. Bonus tùy chọn, chưa thực hiện. Đã có reflection do AI hỗ trợ soạn và 14 ảnh bằng chứng; người học cần hiểu, kiểm tra reflection và phần khai AI trước khi nộp.
