# Bonus A: Lakehouse cho LLM observability

Hoàng Thái Đạt | 2A202602959 | K4-Track02-Day18 | Bản thiết kế để review, 05/10/2026

## 1. Problem statement

Hệ thống ghi 1 tỷ request/ngày, khoảng 5 KB mỗi request: 5 TB raw/ngày. Dashboard cost và latency theo tenant phải refresh mỗi 5 phút. Prompt/response đầy đủ sau redaction được đọc trong 7 ngày; sau đó chỉ aggregates được phục vụ, giữ 1 năm. PII phải bị redact trước mọi lượt đọc của con người. Ngân sách storage tối đa 5.000 USD/tháng. Khó khăn là vừa ingest liên tục, xử lý replay và cập nhật đến muộn, vừa xóa dữ liệu trong snapshot cũ mà không phá reader. Tôi chọn Iceberg trên S3, dùng Gold phục vụ dashboard. Budget được kiểm tra cả tháng 31 ngày và tính toàn bộ Kinesis vào storage một cách bảo thủ. Đây là thiết kế có điều kiện nghiệm thu, chưa phải bằng chứng chạy được ở quy mô 1 tỷ request/ngày.

### Phạm vi và giả định để kiểm chứng

Region **us-east-1**, USD trước thuế, không discount; 10.000 tenant hoạt động, tối đa 3 model/tenant. KB/TB đầu vào dùng hệ thập phân; S3 quy đổi sang GiB tính phí. Peak giả định 5 lần trung bình; 5 KB đã gồm key/envelope. Bronze và Silver cần nén thực đo **ít nhất 4:1**, Gold 2:1; Silver 1 KB/event. Những số này là giả định thiết kế, không phải đặc tính đảm bảo của Zstd.

### Một sơ đồ kiến trúc

```text
API producers: event_id = request_id + attempt_id; revision tăng
   | TLS; gateway REDACT trước lưu bền vững; không log raw PII
   v
Kinesis: 350 shards, 24h buffer, salted key, shared consumer
   | Glue Spark: batch 60s; checkpoint + replay
   v
BRONZE / Iceberg / S3 Standard: payload đã redact, 7d đọc
   | schema contract + revision-aware MERGE + dedup event_id
   v
SILVER / Iceberg: metadata 7d; day(ts), bucket(32, tenant)
   | sort tenant/ts; compact; ACID snapshot; lineage snapshot ID
   v
GOLD / Iceberg: tenant/model/5-minute aggregates, TTL 365d
   | API cache recent windows --> tenant dashboard, refresh <=5m
   +--> Athena qua query broker --> bounded historical queries
Query broker --> Bronze/Silver incident review: tenant + TTL gate
Glue Catalog + IAM/KMS: registry, restricted readers/writer
Maintenance: expire snapshots -> orphan GC; protect live readers
```

**Ingest và query.** Trung bình 11.574 req/s; peak 57.870 req/s, 289,35 MB/s. 350 shards cấp 350 MB/s bảo thủ, dư 20,96%; giới hạn shard và key được [AWS mô tả](https://docs.aws.amazon.com/streams/latest/dev/key-concepts.html). Producer retry cùng event ID; ACK log chỉ sau Kinesis nhận. Gold giữ count, token sums, error count, cost ở micro-USD và sketch latency; không lấy trung bình các p95. API cache đọc Gold theo snapshot, không chạy Athena cho từng refresh. Broker lấy tenant từ identity và kiểm tra TTL cho cả snapshot lịch sử.

<!-- pagebreak -->

## 2. Quyết định và alternatives đã loại (1-3)

### D1. Table format: Iceberg v2, một Silver writer

**Chọn:** Iceberg cho cả ba tầng; dùng snapshot atomic và MERGE có điều kiện `src.revision > dst.revision`. Một coordinator cấp lease, chỉ một writer Silver hoạt động; khi chuyển lease, dừng writer cũ trước khi chạy writer mới. Retry commit conflict phải reload snapshot và tính lại điều kiện, không chỉ gửi lại file. Schema thay đổi có review, rename theo field ID; không auto-merge field bất kỳ. [Iceberg reliability](https://iceberg.apache.org/docs/latest/reliability/) là cơ sở cho commit, không đảm bảo dedup nghiệp vụ hay transaction nhiều bảng.

**Loại Delta:** có MERGE/time travel tốt, phù hợp lab; nhưng stack này chọn Glue/Athena với Iceberg làm format chung. Chọn Delta sẽ thêm kiểm thử tương thích từng engine và đường bảo trì riêng, chưa có lợi ích đo được để trả chi phí đó. **Loại Parquet thuần:** reader dễ đọc file còn đang viết hoặc đọc lẫn hai lần retry; phải tự xây manifest commit, history và schema ID. Tiết kiệm metadata không bù độ phức tạp publish an toàn.

Silver lưu revision cao nhất cho mỗi event; tenant/model/event_ts bất biến theo event ID, revision chỉ sửa số đo. Nhờ vậy retry không đổi partition/window hoặc kéo dài TTL. Hai dòng cùng revision khác nội dung bị quarantine **đã redact** và báo lỗi. Attempt khác nhau là event khác nhau để không bỏ phí retry inference. Bronze có thể có duplicate vì delivery at least once. Gold tính lại các window bị ảnh hưởng từ Silver snapshot đã pin, rồi overwrite nhóm; không cộng lần nữa vào tổng cũ. Late correction trong 7 ngày được tính lại; cũ hơn bị từ chối tự động, mở incident đối soát thay vì sửa âm thầm.

### D2. Catalog: AWS Glue Data Catalog

**Chọn:** Glue vì không vận hành server catalog riêng, chung registry cho Spark/Athena và quyền AWS; cấu hình credential, optimistic commit và quota phải test với version engine cụ thể. [Glue hỗ trợ đăng ký open table formats](https://docs.aws.amazon.com/glue/latest/dg/populate-otf.html). Catalog không tự làm row isolation: broker và IAM mới là boundary đọc dữ liệu.

**Loại SQLite catalog:** đủ cho PoC nhưng file database local không phục vụ nhiều máy và không thay IAM. **Loại Polaris REST catalog tự host:** có lợi cho đa cloud, nhưng MVP chỉ một AWS region; vận hành HA, upgrade, credential vending và on-call thêm việc ngoài slice một tuần. Chi phí lock-in Glue được chấp nhận; file Iceberg vẫn là định dạng mở để có đường migration sau.

### D3. Layout: ngày UTC + 32 bucket tenant + sort tenant/ts

**Chọn:** Bronze `day(event_ts)`; Silver và Gold thêm `bucket(32, tenant_id)`, sort theo tenant và timestamp. Query bắt buộc tenant và time range. [Hidden partitioning](https://iceberg.apache.org/docs/latest/partitioning/) suy ra ngày từ predicate trên timestamp. Bronze landing ít file theo batch; compact Bronze/Silver thành file mục tiêu 256-512 MiB; Gold compact riêng để không chờ payload. Đây là clustering cho hot path tenant, không gọi sort Iceberg là Z-order.

**Loại partition từng tenant:** 10.000 tenant × ngày làm nhiều partition nhỏ, metadata và PUT tăng; tenant nhỏ khó đạt file đủ lớn. **Loại chỉ partition ngày:** đơn giản nhưng filter một tenant phải mở nhiều file nếu stats chồng lấn. 32 bucket giảm phạm vi, sort giúp min/max bỏ file; hot tenant có thể tách table khi scan/hot-key telemetry chứng minh cần thiết, không tăng bucket vô hạn.

<!-- pagebreak -->

## 3. Quyết định và alternatives đã loại (4-6)

### D4. Compression và tier: Parquet Zstd trên S3 Standard

**Chọn:** Standard cho payload 7 ngày và Gold 1 năm vì cần query trực tiếp. Benchmark nén, CPU decode và scan trên mẫu dữ liệu đã redact; 4:1 cho detail, 2:1 cho Gold là release gate. Raw được gom theo batch, không tạo một S3 object/request. Gold lưu sketch khoảng 4 KB/group trước nén; nghiệm thu sai số p95 không quá 5% so với tổng hợp exact trên fixture.

**Loại Snappy làm mặc định:** CPU nhẹ nhưng chỉ chọn nếu số byte đo được vẫn qua budget; nén 3:1 đã vượt cap tháng 31 ngày. **Loại IA/Glacier cho payload:** retention ngắn gây phí minimum duration và/hoặc latency retrieval; Standard-IA có minimum 30 ngày, Glacier có minimum dài hơn. Gold cần truy vấn trong ngày, chưa có nhu cầu archive. [S3 storage classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html) cung cấp điều kiện tính phí; không cộng một khoản “tiết kiệm tiering” chưa đo.

### D5. Retention: TTL truy cập + snapshot expiry + physical GC

**Chọn:** mọi đường đọc detail chặn tại `event_ts + 7 ngày`, kể cả time travel, cache và signed URL; không phát URL sống quá TTL. Hourly job xóa row hết hạn, expire snapshot và bỏ branch/tag giữ detail; GC kiểm kê cả metadata, staging và object không được reference. Detail bucket không bật versioning/Object Lock; audit ở bucket riêng. Reader detail có lease tối đa 10 phút, writer phải hoàn tất dưới 15 phút; orphan guard tối thiểu 1 giờ và abort writer quá hạn trước sweep. Quy trình phải kiểm tra reference toàn bộ snapshot còn được giữ, không chỉ latest. [Iceberg maintenance](https://iceberg.apache.org/docs/latest/maintenance/) cảnh báo orphan GC quá sớm có thể phá writer.

**Điều kiện review:** 7 ngày là cửa sổ đọc; purge vật lý hoàn tất trong tối đa 24 giờ sau đó. Vì vậy phép tính chứa **8 ngày occupancy**, cộng 25% buffer cho rewrite/duplicate/snapshot. Sau TTL chỉ Gold được query. Nếu đề được hiểu là không còn bất kỳ byte detail nào đúng giây thứ 7 ngày, thiết kế này cần thay cơ chế và nghiệm thu lại; không dùng lời hứa lifecycle để che khoảng trễ. Gold rolling 365 ngày; audit chỉ metadata, không giữ prompt.

**Loại chỉ DELETE/expire snapshot:** data file cũ có thể vẫn tồn tại; NB6 cho thấy expiry và sweep là hai việc. **Loại chỉ S3 lifecycle hoặc giữ mọi snapshot:** lifecycle có thể xóa file vẫn được tham chiếu, hoặc xóa trễ; giữ history vô hạn phá TTL và budget. [S3 expiry](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html) không phải deadline purge chính xác. Rollback luôn qua TTL gate, không hồi sinh prompt hết hạn.

### D6. Governance: redact trước landing, deny direct human read

**Chọn:** gateway redact cả prompt/response, header và exception bằng policy có version; HMAC tenant-scoped cho identifier cần liên kết, key tách tenant, không lưu reverse map. Detector uncertainty chặn ACK log và báo incident, không gửi raw vào DLQ. Bucket private, TLS, SSE-KMS, bucket keys; job role và broker role riêng, IAM giới hạn resource/action; người dùng chỉ qua broker có tenant filter. Audit mọi lượt incident read bằng tenant, purpose, snapshot và redactor version, không log nội dung. CloudTrail data events, access log và CloudWatch dùng để đối chiếu read path theo [S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).

**Loại redact trong Silver:** raw Bronze, stream hoặc error log đã có thể bị đọc. **Loại chỉ encrypt hoặc hash không key:** encrypt không ngăn người có quyền giải mã đọc PII; hash số điện thoại dễ dò, không đủ chống liên kết tenant. Regex chỉ là một lớp; test canary, detector nhiều ngôn ngữ và review mẫu đã kiểm soát là gate trước release.

<!-- pagebreak -->

## 4. Failure modes lúc 3 giờ sáng

### F1. Chết sau commit, trước checkpoint: đếm đôi cost

**Detect:** đối chiếu accepted event ID, Silver unique count và Gold sums theo window; alert bất kỳ chênh lệch integer micro-USD hoặc revision conflict. **Recover/rollback:** reload catalog, replay offset chưa ACK; MERGE lọc revision, Gold tính lại nhóm từ snapshot Silver. Nếu Gold sai, phục vụ snapshot Gold tốt đã pin, rồi rebuild nhóm và publish snapshot mới. PoC tái hiện điểm chết này, đồng thời thử revision 2 đến trước bản replay revision 1; không dựa vào exactly-once của stream.

### F2. GC xóa file đang được reader dùng (Day18 time travel)

**Detect:** `NoSuchKey`, reader failure, inventory thiếu live reference hoặc purge backlog >24 giờ; alert ngay, không đợi dashboard. **Recover/rollback:** disable sweep, abort batch GC, giải phóng/đợi lease, quay query về snapshot đã kiểm tra file còn đủ. Nếu file đã mất thì time travel không cứu được: replay dữ liệu vẫn trong Kinesis 24 giờ, hoặc source có khả năng retry, rebuild affected partitions. Nếu cả hai không còn, khai báo mất dữ liệu và khóa release; không hứa restore từ file đã xóa. Dry-run GC phải cho 0 live references trước khi chạy thật.

### F3. Schema evolution làm sai cost hoặc mất cột

**Detect:** contract version mismatch, field ID/type diff, cost không nguyên hoặc reconciliation lệch; canary query trước publish. **Recover/rollback:** dừng writer mới, pin Gold snapshot trước thay đổi, rollback binary/contract; replay batch đã redact còn trong retention bằng schema cũ. Rename giữ field ID; drop/type narrowing cần migration hai bước. Ghi `source offsets + silver_snapshot_id + gold_snapshot_id + code_sha` vào lineage để chỉ rebuild các window bị ảnh hưởng.

### F4. Hot tenant làm đầy shard, lag vượt 5 phút

**Detect:** `WriteProvisionedThroughputExceeded`, iterator age >120 giây hoặc event-to-visible >300 giây. Theo dõi byte/key và tenant skew, không chỉ trung bình stream. **Recover/rollback:** producer exponential retry với jitter cùng ID, salt key theo event; rollback partition-key deploy nếu tạo skew. Freeze backfill/compaction trước khi lấy thêm compute. Scaling shard ngoài 350 phải chạy lại cost gate; nếu backlog gần 24 giờ thì incident và producer backpressure, không âm thầm drop log. Outage quá 24 giờ nằm ngoài khả năng replay đã cấp ngân sách.

### F5. Redactor lọt PII hoặc quyền tenant bị bỏ qua

**Detect:** canary PII marker trong output, DLP scan, tenant A truy vấn tenant B phải bị deny; audit thiếu broker identity báo động. **Recover/rollback:** chặn đọc affected tables/cache, revoke broker session/URL, rollback redactor/policy; reprocess từ bản **đã redact** nếu còn đủ thông tin, nếu không thì delete affected payload và khai báo mất khả năng incident review. Không giữ raw để “sửa sau”. Quét cả snapshot cũ, log và staging; break-glass không được bypass TTL/redaction.

### F6. Nén kém, rewrite tăng hoặc bill sắp vượt cap

**Detect:** byte inventory hằng ngày + forecast tháng 31 ngày, PUT/GET counters, compression ratio từng tenant; warn ở forecast 4.800 USD, block scale-out nếu >5.000. **Recover/rollback:** pause compaction gây amplification, rollback layout/compression regression, giới hạn ad-hoc scan, thử codec/cấu hình batch trên mẫu trước rollout. Không giảm retention hoặc bỏ event để báo đạt budget. Nếu forecast vẫn vượt, giữ service hiện có và báo constraint breach; production release chỉ sau benchmark hoặc sửa kiến trúc được review. Budget alarm là detection, không phải cơ chế hard cap tự động.

<!-- pagebreak -->

## 5. Chi phí: số học, assumptions và độ nhạy

Giá public kiểm tra **05/10/2026**, us-east-1. [`cost_model.py`](tools/cost_model.py) dùng Decimal, chạy offline với [S3 price evidence](evidence/aws-s3-price-evidence.json); [kết quả đầy đủ](evidence/cost-model.json) chứa cả các case thất bại. S3 offer version 20260928230416. Không dùng số đo PoC nhỏ để suy ra throughput production.

### Storage ở steady state, Gold đã đủ một năm

| Khoản dung lượng | Phép tính, TB thập phân | TB |
|---|---|---:|
| Bronze detail | 5 TB/ngày × 8 ngày / 4 | 10,0000 |
| Silver metadata | 1 TB/ngày × 8 ngày / 4 | 2,0000 |
| Rewrite, replay, history | (10 + 2) × 25% | 3,0000 |
| Gold | 10.000 × 3 × 288 × 365 × 4.000 B / 2 / 10^12 | 6,3072 |
| Audit, checkpoint, metadata, results | gồm history/rewrite Gold <=24h; không raw PII | 1,0000 |
| Tổng S3 | 22,3072 × 10^12 / 1024^3 | 20.775,20 GiB |

| Khoản storage/buffer | Phép tính tháng 30 ngày | USD |
|---|---|---:|
| S3 Standard | 20.775,20 GiB × 0,023 USD/GiB-tháng | 477,83 |
| PUT/LIST và GET | 8M × 0,005/1.000 + 30M × 0,0004/1.000 | 52,00 |
| Kinesis, tính toàn bộ vào cap | 350 × 720h × 0,015 + 30.000M PUT units × 0,014/M | 4.200,00 |
| Storage contingency | KMS/storage variance allowance | 100,00 |
| **Tổng so với cap 5.000** | **477,83 + 52 + 4.200 + 100** | **4.829,83** |

S3 rates từ [AWS S3 pricing](https://aws.amazon.com/s3/pricing/) và JSON evidence; [Kinesis pricing](https://aws.amazon.com/kinesis/data-streams/pricing/) tính unit 25 KB, giả định mỗi event <=25 KB. 350 shards giữ 24 giờ; không extended retention, không enhanced fan-out. Shared consumer không có khoản retrieval riêng trong mô hình này. Request allowance dựa trên coalesce 32 bucket/batch 60s và compaction, phải đo lại; duplicate/rewrite vượt 25% cũng phải chạy lại model.

### Compute và vận hành: tách khỏi cap storage

| Khoản | Phép tính tháng 30 ngày | USD |
|---|---|---:|
| Gateway redact, 12 tasks 8 vCPU/16 GB | 12 × (8 × 0,000011244 + 16 × 0,000001235) × 2.592.000s | 3.412,48 |
| Dashboard API, 2 tasks 2 vCPU/4 GB | 2 × (2 × CPU-rate + 4 × RAM-rate) × 2.592.000s | 142,19 |
| Glue streaming, cả Bronze/Silver/Gold | 16 DPU × 720h × 0,44 | 5.068,80 |
| Glue maintenance | 8 DPU × 4h/ngày × 30 × 0,44 | 422,40 |
| Athena ad-hoc quota | 30 TB billed scan × 5 USD/TB | 150,00 |
| Ops allowance | catalog, audit ingestion, metrics, endpoints/network | 500,00 |
| **Compute + ops / tổng hệ thống** | **Không cộng Kinesis lần hai** | **9.695,87 / 14.525,70** |

Rates: [Fargate Linux/x86](https://aws.amazon.com/fargate/pricing/), [Glue](https://aws.amazon.com/glue/pricing/), [Athena](https://aws.amazon.com/athena/pricing/). Fargate không thêm storage >20 GB/task. Ops 500 USD là allowance, không phải quote; traffic nội vùng qua S3 gateway endpoint, không đẩy payload qua NAT/cross-region. Không bao gồm inference, nhân sự, DR hay export payload ra Internet; phải thêm nếu đổi scope. Gateway giả định <=1 ms CPU/event, 96 vCPU; Glue 16 DPU là capacity hypothesis cần load test.

**Stress 31 ngày:** storage **4.971,56**, dư **28,44** ngoài reserve; compute/ops **10.019,06**, tổng **14.990,63 USD**. Cùng tháng, nén 3:1 -> **5.078,67**; 2:1 -> **5.292,87**; 20K tenant -> **5.106,67 USD** storage, đều vượt cap. Chỉ cho rollout khi compression/occupancy/request và peak đã đo đạt model; cap storage không có nghĩa tổng hệ thống <=5.000 USD.

<!-- pagebreak -->

## 6. MVP một tuần và bằng chứng khả thi

Slice shippable: 2 tenant, 3 model, một region; telemetry đã redact -> Iceberg -> dashboard tenant, replay và TTL có gate. Chưa build HA đa region hay toàn bộ 1 tỷ event/ngày. Prodscale là bước nghiệm thu riêng sau slice.

| Ngày | Kết quả giao được |
|---|---|
| 1 | Contract event/revision, threat/read-path inventory, canary PII, fixtures có replay và late event |
| 2 | Gateway redact + Kinesis thử nghiệm; tenant-salted key, retry ACK, lag metrics |
| 3 | Bronze/Silver Iceberg, conditional MERGE, conflicting revision quarantine, pinned-snapshot lineage |
| 4 | Gold 5-minute count/token/cost/sketch; API cache, tenant identity filter và freshness timestamp |
| 5 | TTL cho current/history/cache, GC dry-run với live reader/writer, time-compressed retention test |
| 6 | Kill sau commit/trước checkpoint, stale replay, schema regression, load/skew/compression tests |
| 7 | Đối soát và cost forecast, runbook rollback, demo + go/no-go review |

### Tiêu chí nghiệm thu và mechanism khó nhất

**Correctness:** ít nhất 100K event, 10% replay, 1% correction tới muộn hoặc ngược revision; Silver đúng ID/revision, Gold count và micro-USD bằng tổng hợp độc lập. Crash tại Bronze commit, Silver commit và Gold publish trước checkpoint; restart vẫn ra cùng Gold. Mỗi Gold snapshot ghi Silver input snapshot + code SHA; API một refresh đọc một snapshot. PoC dưới đây chỉ kiểm tra điểm crash Silver, không giả vờ đã test cả pipeline AWS.

**Freshness và scale:** ở slice, p99 event accepted -> Gold visible <=300 giây trong 60 phút chạy liên tục, không backlog tăng. Ngân sách latency: buffer 60s + Silver 90s + Gold 90s + publish/cache 60s. Trước production, load 57.870 req/s với payload 5 KB và tenant skew, đo throttling/CPU/nén; 16 DPU phải đạt pipeline latency này, gateway <=1 ms CPU/event. Không suy tuyến tính từ laptop; thiếu kết quả thì chưa release production.

**Security/retention:** 0 canary PII lọt vào stream/table/log trong bộ test đã định nghĩa; tenant A không đọc được B qua API, Athena, snapshot cũ hoặc URL. Đồng hồ giả lập ngay trước/sau TTL phải đúng; reader lease và writer bị kill trong lúc GC không làm mất live file. Sau TTL detail không đọc được, physical inventory sạch trong 24h, Gold sống đủ 365d. Đây là test policy/fixtures, không chứng nhận không còn PII bất kỳ trên mọi dữ liệu tự do.

**FinOps:** lấy mẫu payload đại diện đã redact, đo tỷ số trên file thực gồm metadata; baseline >=4:1 detail, >=2:1 Gold, rewrite/replay <=25%, 8M PUT/LIST và 30M GET/tháng, 1 TB ancillary. Forecast 31 ngày <=5.000 USD kể cả Kinesis và reserve; các case thất bại phải được báo. Đạt toàn bộ gates mới bảo vệ thiết kế production.

### PoC đã chạy: replay + late revision + snapshot lineage

[`poc/replay_safe.py`](poc/replay_safe.py) là notebook Jupytext ngắn, bản [ipynb có output](poc/replay_safe.ipynb) chạy bằng PyIceberg 0.12.0/PyArrow 25.0.1. SQLite catalog thay Glue ở local. Kết quả: crash sau commit được bắt; reload thấy **2 dòng**; replay thêm **0 dòng**; revision cũ bị bỏ qua; same-revision/different-content bị chặn; Gold mới **2 request, 350 micro-USD**, snapshot cũ **300**; publish lặp cho nội dung giống nhau; Gold ghi đúng Silver snapshot ID. [Evidence](evidence/poc-result.json) được trích từ output thực thi.

Giới hạn: một writer, fixture nhỏ, không có Kinesis/AWS IAM, không load test hay physical GC production; hàm đọc toàn Silver chỉ phù hợp spike. Production phải index/filter affected IDs/partitions và recompute affected windows, không full-scan 1B dòng mỗi phút. Cách tái lập, checksums và validation ở [README bonus](README.md). Đây là bài cá nhân có AI hỗ trợ khai trong [AI_USAGE](../AI_USAGE.md), chưa commit/push hoặc tạo PR.
