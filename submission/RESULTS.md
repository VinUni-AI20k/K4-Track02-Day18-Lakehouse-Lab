# Kết quả phần bắt buộc

Số liệu trích từ các notebook đã thực thi; dữ liệu đầu vào do scripts của đề bài sinh.

## NB1 — 01_delta_basics

```text
Schema enforcement blocked: True; failed write left v0 and 3 rows unchanged
Schema after merge: ['id', 'name', 'age', 'city', 'tier']
Tier groups: [('premium', 1), (None, 3)]
Log directory: /home/huyhoangg/repo/vinai/K4-Track02-Day18-MaiHuyHoang-2A202602685-Lakehouse-Lab/_lakehouse/scratch/users_delta/_delta_log
JSON commits: ['00000000000000000000.json', '00000000000000000001.json']
Commit v0 contents:
{"commitInfo":{"timestamp":1791133861011,"operation":"WRITE","operationParameters":{"mode":"Overwrite"},"engineInfo":"delta-rs:py-1.6.6","operationMetrics":{"num_added_files":1,"num_removed_files":0,"num_partitions":0,"num_added_rows":3,"execution_time_ms":3,"num_retries":0},"clientVersion":"delta-rs.py-1.6.6"}}
{"protocol":{"minReaderVersion":1,"minWriterVersion":2}}
{"metaData":{"id":"98f8a9a3-3183-4d16-84a5-846db7468804","name":null,"description":null,"format":{"provider":"parquet","options":{}},"schemaString":"{\"type\":\"struct\",\"fields\":[{\"name\":\"id\",\"type\":\"long\",\"nullable\":true,\"metadata\":{}},{\"name\":\"name\",\"type\":\"string\",\"nullable\":true,\"metadata\":{}},{\"name\":\"age\",\"type\":\"long\",\"nullable\":true,\"metadata\":{}},{\"name\":\"city\",\"type\":\"string\",\"nullable\":true,\"metadata\":{}}]}","partitionColumns":[],"createdTime":1791133861007,"configuration":{}}}
{"add":{"path":"part-00000-f2719960-85f8-423b-b190-f280317b06db-c000.snappy.parquet","partitionValues":{},"size":1384,"modificationTime":1791133861011,"dataChange":true,"stats":"{\"numRecords\":3,\"minValues\":{\"name\":\"alice\",\"id\":1,\"city\":\"Danang\",\"age\":25},\"maxValues\":{\"age\":35,\"id\":3,\"name\":\"charlie\",\"city\":\"Hanoi\"},\"nullCount\":{\"age\":0,\"name\":0,\"city\":0,\"id\":0}}","tags":null,"baseRowId":null,"defaultRowCommitVersion":null,"clusteringProvider":null}}
```

Delta ghi transaction vào JSON log. Ghi age='thirty' bị chặn và không tăng version hay số dòng. Thêm tier cần schema_mode='merge'; dữ liệu cũ có tier=NULL, dữ liệu mới có premium nên query trả hai nhóm. Bằng chứng dưới đây gồm đường dẫn log và nguyên văn commit v0.

## NB2 — 02_optimize_zorder

```text
Files before=200; after compact+ZORDER=55
Median before=71.186 ms; after=13.102 ms; speedup=5.43x
Target user=4242; candidate files=1/55; pruning=55.00x
Candidate user_id ranges: [(3696, 5534)]
```

200 micro-batch tạo 200 file nhỏ. Compaction giảm số file; Z-order gom user_id để min/max loại file không chứa 4242. Pruning ratio là tổng file sau tối ưu chia số file có khoảng chứa user đích; đây là file có thể cần đọc, không phải số dòng khớp. Speedup dùng median ba lần, có thể biến động do cache và tải máy; rubric chấp nhận speedup ≥3× hoặc pruning ≥10×.

## NB3 — 03_time_travel

```text
MERGE 100K metrics: {'num_source_rows': 100000, 'num_target_rows_inserted': 50000, 'num_target_rows_updated': 50000, 'num_target_rows_deleted': 0, 'num_target_rows_copied': 50000, 'num_output_rows': 150000, 'num_target_files_scanned': 1, 'num_target_files_skipped_during_scan': 0, 'num_target_files_added': 1, 'num_target_files_removed': 1, 'execution_time_ms': 40, 'scan_time_ms': 29, 'rewrite_time_ms': 5}
Time travel v0 rows=100000; current rows=150000; score<0=0
History after RESTORE:
v4: RESTORE
v3: WRITE
v2: MERGE
v1: WRITE
v0: WRITE
```

MERGE xử lý 100.000 dòng nguồn: 50.000 update và 50.000 insert, thành 150.000 dòng. Time travel v0 vẫn có 100.000 dòng. RESTORE về trạng thái v2 tạo commit v4, giữ lịch sử v0–v3; số dòng score<0 hiện tại phải bằng 0.

## NB4 — 04_medallion

```text
Storage: Bronze=/home/huyhoangg/repo/vinai/K4-Track02-Day18-MaiHuyHoang-2A202602685-Lakehouse-Lab/_lakehouse/bronze/llm_calls_raw
Silver=/home/huyhoangg/repo/vinai/K4-Track02-Day18-MaiHuyHoang-2A202602685-Lakehouse-Lab/_lakehouse/silver/llm_calls
Gold=/home/huyhoangg/repo/vinai/K4-Track02-Day18-MaiHuyHoang-2A202602685-Lakehouse-Lab/_lakehouse/gold/llm_daily_metrics
Bronze=200000; Silver=190052; dropped=9948
Gold: 7 dates x 3 models = 21 rows
date,model,p50_latency_ms,p95_latency_ms,cost_usd,error_rate
2026-04-01,claude-haiku-4-5,563.0,1131.0,46.4103664,0.04882503348350176
2026-04-01,claude-opus-4-7,3008.0,6039.400000000001,284.77728,0.05012996658002228
2026-04-01,claude-sonnet-4-6,1381.0,2751.6499999999996,345.488508,0.05046660117878193
2026-04-02,claude-haiku-4-5,578.0,1142.0499999999993,46.2543768,0.04925925925925926
2026-04-02,claude-opus-4-7,3013.0,5950.800000000001,295.02204,0.05244381020335355
2026-04-02,claude-sonnet-4-6,1384.0,2739.0,345.211167,0.04931523674998465
2026-04-03,claude-haiku-4-5,563.0,1130.4499999999998,45.3099808,0.04804804804804805
2026-04-03,claude-opus-4-7,3058.0,5959.900000000001,293.05839000000003,0.045087976539589444
2026-04-03,claude-sonnet-4-6,1391.0,2744.0,348.6405,0.04603658536585366
2026-04-04,claude-haiku-4-5,553.0,1124.0,44.5938976,0.049981162878312196
2026-04-04,claude-opus-4-7,2981.0,5907.5999999999985,289.77705000000003,0.05401512423478574
2026-04-04,claude-sonnet-4-6,1372.0,2742.0,346.09596,0.04989351992698509
2026-04-05,claude-haiku-4-5,567.0,1134.0,46.3346856,0.05072907731895601
2026-04-05,claude-opus-4-7,3098.0,5964.5,284.065965,0.04696235557212076
2026-04-05,claude-sonnet-4-6,1370.0,2735.0,344.42634599999997,0.05230202578268876
2026-04-06,claude-haiku-4-5,562.0,1135.4499999999998,45.6989696,0.045499262174126906
2026-04-06,claude-opus-4-7,3102.0,6021.0,284.95812,0.05549220828582288
2026-04-06,claude-sonnet-4-6,1379.0,2746.0,345.844923,0.05050073277967758
2026-04-07,claude-haiku-4-5,566.0,1124.2999999999993,46.666379199999994,0.050030138637733576
2026-04-07,claude-opus-4-7,2993.0,5987.599999999999,282.67893000000004,0.06153846153846154
2026-04-07,claude-sonnet-4-6,1395.0,2754.8499999999985,343.470975,0.04887264618434093

Gold checks: {'Bronze/Silver/Gold present on storage': True, 'Silver < Bronze': True, 'Gold covers every date x 3 models': True, 'p50 <= p95 and both populated': True, 'positive cost and valid error_rate': True}
```

Bronze giữ 200.000 bản ghi thô. Silver chọn lần xuất hiện đầu theo request_id, loại retry trùng và partition theo ngày. Gold tổng hợp từng ngày/model, tính percentile liên tục p50/p95, tỷ lệ status khác ok và chi phí theo bảng giá minh họa có sẵn trong lab. Kiểm tra đủ mọi cặp ngày/model, p50≤p95, cost>0 và error_rate∈[0,1]. Đây là dữ liệu giả, không phải benchmark hay giá dịch vụ hiện hành.

## NB5 — 05_iceberg_catalog

```text
Catalog=SqlCatalog; table=('lake', 'llm_events'); day(ts) partition
Plan files: all=10; one day=1; pruning=10.0x
Metadata=139261 bytes; data=48419 bytes; metadata:data=2.8762
Tree: metadata JSON -> 10 snapshot manifest lists -> 10 manifests -> 10 data files (before evolution)
Field IDs after rename: [(1, 'event_id'), (2, 'ts'), (3, 'model'), (4, 'latency_millis'), (5, 'cost_usd'), (6, 'tier')]
Partition spec IDs in use: [1, 2]
Rows across specs: 5500
```

SqlCatalog SQLite quản lý namespace, đăng ký bảng và con trỏ metadata. day(ts) cho phép filter trực tiếp trên ts; plan_files chọn file một ngày thay vì cả 10 ngày. Rename latency_ms giữ field_id=4 và không rewrite dữ liệu. Spec mới thêm model cùng tồn tại với spec cũ; vẫn đọc được 5.500 dòng. Metadata:data được tính bằng tổng byte metadata chia byte data; tỷ lệ cao ở bảng nhỏ không thể suy ra trực tiếp cho production. Phép tính chi phí trong notebook là giả định minh họa của đề.

## NB6 — 06_maintenance

```text
Compaction: 200 -> 11 files; 18.18x fewer
Clustering: touched 11 -> 1/10; skip=90.00%
Delta vacuum reclaimed=16904647 bytes
Delta orphans found/removed=3; remaining=0
Iceberg snapshots=20 -> 3; avro before/after expiry=40/40
Stranded manifest lists removed=17; reclaimed=37997 bytes; remaining=0
Checkpoint: ['00000000000000000199.checkpoint.parquet', '00000000000000000099.checkpoint.parquet', '00000000000000000203.checkpoint.parquet']
_last_checkpoint: True
Current Delta rows: 100000
Current Iceberg rows: 2000
```

Compaction giảm file live nhưng tạm tăng dung lượng vật lý vì file cũ được tombstone. Clustering được đo bằng min/max, không chỉ stopwatch. VACUUM thu hồi file đã tombstone, nhưng trong delta-rs phiên bản đang chạy không tìm ba orphan chưa commit; phép hiệu file trên đĩa và file được tham chiếu, có age guard, tìm và xóa chúng. PyIceberg expiry giảm 20→3 snapshot nhưng chưa xóa manifest list vật lý; sweep riêng dọn file stranded. Các phép dọn chỉ chạy trên bảng scratch của lab; production cần bảo vệ cả snapshot còn giữ và writer đang chạy. Checkpoint và _last_checkpoint hỗ trợ reader giảm replay JSON.

## NB7 — 07_vectors_multimodal

```text
Row group=200 rows / 13110466 bytes; blob=65536 bytes; amplification=200.05x
Float32=2685240 bytes; int8=462726 bytes; ratio=5.803x
Recall@10=0.904; topic fidelity=1.000
SQL top-5 neighbours: [(7, 'storage-note-00007', 'storage', 1.0), (1703, 'storage-note-01703', 'storage', 0.779325544834137), (1200, 'storage-note-01200', 'storage', 0.7769769430160522), (766, 'storage-note-00766', 'storage', 0.7764201164245605), (1250, 'storage-note-01250', 'storage', 0.7683840990066528)]
Lifecycle: erased docs in table=0; stale external index=8; CDF deletes=8
```

Amplification dùng byte row group trong footer chia kích thước một blob; đây là ước lượng theo granularity row group, không phải đo byte mạng của một truy vấn. Query chỉ chọn topic tránh đọc blob nhờ column pruning. int8 tiết kiệm dung lượng nhưng phải kiểm tra recall@10 và topic fidelity trên 100 query của corpus giả; self-match được giữ theo bài mẫu. SQL cast list<float> thành FLOAT[256] vì đường Delta không giữ fixed-size vector. Xóa user_042 làm in-table hết hit nhưng external index cũ vẫn còn hit; CDF mang doc_id của delete để index có thể đồng bộ. Notebook minh họa feed, chưa triển khai consumer tự đồng bộ.

## NB8 — 08_agents_provenance

```text
Silver partitions: ['agent_version=policy-v2', 'agent_version=policy-v3']
Gold policies: [{'agent_version': 'policy-v2', 'trajectories': 150, 'success_rate': 0.76, 'avg_steps': 5.26, 'avg_cost_usd': 0.06915, 'total_cost_usd': 10.37, 'avg_seconds': 16.2}, {'agent_version': 'policy-v3', 'trajectories': 150, 'success_rate': 0.753, 'avg_steps': 5.26, 'avg_cost_usd': 0.06928, 'total_cost_usd': 10.39, 'avg_seconds': 15.7}]
Pinned version=0; training steps=1578; replay steps=1578
5 list_tables calls -> 1 catalog read; destructive call=input_required; task=completed
Provenance partitions: ['provenance_bucket=UNCLASSIFIED', 'provenance_bucket=licensed', 'provenance_bucket=public_domain', 'provenance_bucket=scraped_optout_checked', 'provenance_bucket=synthetic']
Trainable=1666/2000; excluded UNCLASSIFIED=334
Current-version deletion of user_007: 8 -> 0; version 0 -> 1
```

Silver partition theo hai agent_version, Gold có cả hai policy. Training pin version trước append; replay đối chiếu số bước, chưa chứng minh equality toàn bộ nội dung. Lớp MCP chạy offline: năm list_tables chỉ đọc catalog một lần, destructive call trả input_required, task polling hoàn tất. confirmed do caller truyền và delete_rows là no-op, nên không phải authorization production hay MCP server thật. Bốn bucket là fixture minh họa; CC-BY-4.0 cần ghi công, không phải public domain, và consent không chứng minh đã kiểm tra scraping opt-out. UNCLASSIFIED bị loại khỏi trainable set. Xóa subject chỉ xác nhận version hiện tại; version cũ vẫn chứa dữ liệu.
