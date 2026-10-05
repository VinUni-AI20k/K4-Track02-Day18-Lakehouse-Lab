# Giải thích kết quả Lakehouse Lab

Trần Đại Nhân · 2A202602642. Số đo chính xác của từng lần chạy nằm trong
`evidence/execution.json`, output notebook và `logs/`. Các số thời gian phụ thuộc máy.

## NB1 — Transaction log và schema

Delta lưu dữ liệu trong Parquet và trạng thái bảng trong `_delta_log`.
Commit v0 chứa `protocol`, `metaData`, `add` và `commitInfo`; commit tiếp theo
thêm dòng cùng cột `tier`. Schema enforcement từ chối `age='thirty'` vì không
chuyển được sang kiểu số nguyên. Kiểm tra bổ sung xác nhận lần ghi lỗi không
tăng version, không tăng số dòng; cờ PASS lấy từ exception thực tế.

`schema_mode="merge"` cho phép thêm `tier`, còn ba dòng cũ có NULL. Vì vậy
GROUP BY trả hai nhóm: premium và NULL. Evolution phải opt-in, không có nghĩa
là engine tự cho phép mọi thay đổi kiểu. Nội dung commit JSON được in nguyên
văn để phân biệt transaction thật với việc chỉ tạo thư mục mang tên Delta.

## NB2 — Compaction và Z-order

200 lần append tạo 200 file nhỏ (đạt ngưỡng ≥ 100). OPTIMIZE + Z-order còn 55
file; khoảng min/max `user_id` của mỗi file hẹp và gần như không chồng nhau, nên
predicate `user_id=4242` chỉ còn 1 file ứng viên: pruning 55×.
`pruning_ratio = files_after / candidate_files` đo số file phải xét so với số
file còn khả năng chứa kết quả, không phải tỷ lệ file trước và sau compaction.
Trước Z-order, `user_id` ngẫu nhiên nên file nào cũng có min/max phủ gần hết
miền giá trị; stats tồn tại nhưng không loại được file nào.

Benchmark lấy median ba lần; cache, SSD và tải CPU làm speedup biến động.
Rubric chấp nhận speedup ≥ 3 hoặc pruning ≥ 10, không yêu cầu cả hai. Target
256 KiB chỉ phục vụ dữ liệu lab: gộp hết thành một file sẽ mất khả năng file
skipping. Không suy ra cấu hình file production hoặc SLA từ benchmark này.

## NB3 — MERGE và RESTORE

MERGE nhận 100.000 dòng, cập nhật 50.000 ID đã có và chèn 50.000 ID mới,
tạo bảng 150.000 dòng tại v2. Các operation metrics được kiểm tra trực tiếp.
Append dữ liệu xấu tạo v3 với 50 dòng score âm. RESTORE về nội dung v2 tạo
transaction mới v4, giữ lịch sử v0–v3; history cuối có năm version.

Version cũ v0 vẫn đọc được 100.000 dòng. Bảng hiện tại sau RESTORE có 150.000
dòng và không còn score âm. Đây là khôi phục trạng thái có audit trail,
không phải xóa lịch sử. Time travel chỉ khả dụng khi log và các file cần thiết
còn tồn tại; vacuum sai retention có thể làm việc khôi phục này thất bại.

## NB4 — Bronze, Silver và Gold

Bronze chứa 200.000 sự kiện tổng hợp với request retry. Silver giữ sự kiện có
timestamp sớm nhất cho mỗi `request_id`: còn 190.052 dòng, bỏ đúng 9.948 bản
retry mà generator đã gieo, và ID trở thành duy nhất. Gold tổng hợp đủ 7 ngày
UTC × 3 model = 21 dòng, mỗi cặp ngày/model đúng một dòng.
NB4 tính độc lập bằng Polars để so với DuckDB cho từng nhóm: p50/p95 dùng
nội suy linear, tổng token, tỷ lệ lỗi và chi phí theo giá minh họa.

Lần chạy đầu trên máy UTC+7 cho ra 8 "ngày": `CAST(ts AS DATE)` với
`TIMESTAMPTZ` đổi theo múi giờ session của DuckDB, nên ngày 01/04 chỉ có 17 giờ
dữ liệu và 08/04 chỉ 7 giờ. Gold như vậy vẫn qua ngưỡng ≥ 7 ngày nhưng sai
nghĩa (hai ngày thiếu giờ trông như lưu lượng giảm) và đổi theo máy chạy.
Notebook đã cố định `AT TIME ZONE 'UTC'` và kiểm tra cột `date` bằng ngày UTC
của `ts`; tổng cost giữ nguyên 4.754,78 USD trước và sau, chứng tỏ chỉ thay đổi
cách gom nhóm, không mất dòng.

Kiểm tra còn xác nhận không NULL, p50 ≤ p95, cost dương, error_rate trong
[0,1], và cả ba bảng có transaction log trên đĩa. Giá và tên model là fixture
của đề, không phải bảng giá API hiện hành. Generator chỉ sinh JSON hợp lệ;
pipeline hiện fail fast với JSON hỏng, chưa có quarantine cho dữ liệu thật.

## NB5 — Catalog, field ID và partition evolution

SQLite SqlCatalog đăng ký bảng và vị trí metadata. Lọc một ngày bằng `ts`
làm scan planner chọn một file trong mười file nhờ transform `day(ts)`
(pruning 10×); người viết query không cần biết cột partition `ts_day`. Với
Hive-style partition, người quên thêm predicate trên cột partition sẽ đọc đủ
10 file, tức gấp 10 lần I/O cho mọi truy vấn theo ngày. Pruning được đo bằng
`plan_files()`, không suy ra từ thời gian query.

Metadata tree đi từ catalog qua metadata JSON, manifest list, manifest rồi
đến data file. Tỷ lệ báo cáo là metadata bytes / data bytes, không phải phần
trăm metadata trên tổng metadata + data. Ở đây metadata (~140 KB) lớn gấp
khoảng 2,9 lần data (~48 KB) vì bảng chỉ 5.500 dòng mà mỗi commit vẫn thêm
metadata JSON, manifest list và manifest; với data cỡ GB/TB tỷ lệ này nhỏ
hơn nhiều, nhưng nếu commit quá thường xuyên thì metadata vẫn tăng nhanh và
cần expiry. Rename `latency_ms` thành
`latency_millis` giữ field ID 4. Thêm partition theo model để spec 1 và 2 cùng
tồn tại; đọc đủ 5.500 dòng chứng minh layout cũ vẫn dùng được. Catalog local
chưa cung cấp auth, governance hay scan planning từ server.

## NB6 — Maintenance và phạm vi an toàn

Compaction thay 200 file nhỏ bằng 11 file (18,2×, ngưỡng 10×); file cũ vẫn
nằm trên đĩa để reader cũ và time travel sử dụng, nên bytes vật lý tạm tăng.
Z-order làm stats hữu ích cho point query: chỉ 1/10 file có min/max chứa giá
trị cần tìm, tức bỏ qua 90% file mà không cần mở. VACUUM sau đó thu hồi
khoảng 16,9 MB file đã tombstone; nhưng nó chỉ thấy file có trong log. Trong phiên bản deltalake ghi ở
requirements-lock, ba file giả lập writer crash không có trong log nên vacuum
không thấy; phép hiệu tập hợp cùng age guard tìm và dọn cả ba.

Với PyIceberg của lần chạy này, expiry giảm 20 snapshot xuống 3 nhưng không
xóa AVRO vật lý; sweep tiếp theo xóa 17 manifest lists bị bỏ lại và vẫn đọc đủ
2.000 dòng. Checkpoint Parquet cùng `_last_checkpoint` được xác nhận trên đĩa.
Đây là hành vi đo của engine/version cụ thể. Delta orphan helper chỉ so với
version hiện tại, nên chỉ an toàn trong scratch đã vacuum lịch sử như lab;
production phải bảo vệ mọi snapshot còn giữ, reader/writer và các reference.

## NB7 — Multimodal, quantization và vòng đời embedding

Pointer giảm lượng dữ liệu cần lấy cho một blob; nó không làm biến mất dung
lượng blob. Analytical projection có thể tránh cột blob ngay với layout inline.
Một row group 200 dòng nặng khoảng 13,1 MB, trong khi một blob chỉ 64 KiB:
muốn lấy một ảnh inline phải đọc cả row group, khuếch đại khoảng 200×.
Amplification của lab được tính từ kích thước row group trong footer so với
một blob, là mô hình I/O theo row group, không phải đo network bytes thực tế;
reader có page index/cache có thể khác. Không lấy số này làm benchmark Lance.

int8 giảm dung lượng trên đĩa 5,8× (khoảng 2,69 MB → 0,46 MB) nhưng đổi thứ
hạng láng giềng: recall@10 = 0,904 (ngưỡng 0,80), topic fidelity = 1,0
(ngưỡng 0,95). Recall@10 so ID với float32,
còn topic fidelity đo cùng chủ đề; cả hai chỉ phản ánh corpus tổng hợp có
cluster và truy vấn có self-match. SQL cosine scan không chứng minh SLA ANN
ở quy mô lớn. Sau xóa subject, bảng trả 0 ID nhưng external index cũ còn 8;
CDF phát đúng 8 delete event. Demo chứng minh index lệch vòng đời, chưa triển
khai consumer đồng bộ hoặc chứng minh xóa vật lý khỏi lịch sử.

## NB8 — Trajectory, version pin và provenance

Silver partition theo hai `agent_version`; Gold có kết quả cho cả hai policy.
Training run pin v0 trước khi append thêm 400 bước vào v1. Replay v0 có 1.578
bước, bằng số đã ghi trong training run, còn version mới có 1.978. Demo kiểm
tra row count, chưa chứng minh equality/hash của toàn bộ nội dung trajectory.

Năm lượt `list_tables` chỉ đọc catalog một lần nhờ cache; đây không phải
cache `tools/list`. `input_required`, `confirmed` và task polling đều mô
phỏng offline; cờ confirmed do caller truyền và delete_rows là no-op, không
phải cơ chế authorization production hay MCP server thực.

Bốn bucket minh họa cùng UNCLASSIFIED thành partition; tập trainable giữ
1.666 dòng và loại đúng 334 dòng UNCLASSIFIED. Các nhãn tuân theo fixture đề, không chứng minh quyền training.
Đặc biệt không dùng nhãn public_domain của fixture CC-BY để suy ra quyền thực.
Xóa subject chỉ loại khỏi version hiện tại; version cũ vẫn giữ dữ liệu.
