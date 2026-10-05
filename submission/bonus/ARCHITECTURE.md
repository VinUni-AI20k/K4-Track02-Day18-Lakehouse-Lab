# Architecture Brief: LLM observability ở quy mô 1B requests/ngày

## 1. Vấn đề và ràng buộc

API foundation model phát sinh 1 tỷ request/ngày, khoảng 5 KB mỗi request/response, tương đương 5 TB/ngày trước nén. Cần dashboard chi phí và latency theo tenant mỗi 5 phút, giữ payload đã khử PII trong 7 ngày để điều tra rồi chỉ giữ aggregate một năm; trần ngân sách hạ tầng là $5.000/tháng. Tải trung bình khoảng 11.600 request/giây (peak giả định 4×). Đây là giả định thiết kế để review, chưa phải số đo production.

**Giả định:** giá US East, một AWS Region; chưa tính VAT, nhân sự, egress hay DR. Làm tròn `TB` thành `TiB` khi tính storage. Khử PII trước khi rời collector; dashboard chỉ cần metrics, không cần prompt/response.

## 2. Sơ đồ kiến trúc

```mermaid
flowchart LR
  A[Model API + telemetry agent] --> B[Fail-closed PII scrubber<br/>tokenize tenant, redact prompt]
  B -->|batched, ZSTD Parquet| C[Bronze Iceberg on S3<br/>hours(ts) + bucket(tenant,16)<br/>7-day payload TTL]
  B -->|small 5-min aggregates only| D[Kinesis Data Streams]
  D --> E[Streaming aggregation job<br/>checkpoint + late-event correction]
  E --> F[Silver Iceberg<br/>typed, deduplicated events<br/>7-day row-level TTL]
  E --> G[Gold Iceberg<br/>tenant × model × 5-min/day metrics]
  E --> H[DynamoDB serving view<br/>latest tenant/model window]
  I[Glue Data Catalog + Lake Formation] -. metadata/access .-> C
  I -. metadata/access .-> F
  I -. metadata/access .-> G
  J[Analyst / dashboard] --> H
  K[Incident analyst, time-limited role] -->|approved, audited query| C
  J -->|ad hoc history| G
```

Bronze giữ payload đã scrub; Silver giữ event chuẩn hóa, không có prompt/response. Streaming xuất Gold và upsert serving view theo `(tenant, model, window_start)`. Dashboard đọc view, phân tích ad hoc đọc Gold; Catalog quản lý metadata và Lake Formation/IAM giới hạn, audit quyền đọc Bronze.

## 3. Quyết định kiến trúc

### Quyết định 1 — Tách payload khỏi luồng dashboard

**Chọn:** collector scrub PII, buffer bền và ghi payload theo lô vào S3 với checksum, manifest, retry idempotent. Kinesis chỉ mang metric tổng hợp 5 phút (tenant token, model, window, count, latency histogram, token total, error count), không mang text.

**Loại Kinesis cho toàn bộ payload:** `5 TiB/ngày × 1.024 GiB/TiB × 30 = 153.600 GiB/tháng`; Standard vào/ra ở $0,08/$0,04 mỗi GB tốn khoảng `$18.432/tháng` cho một consumer, chưa tính stream/storage. Ngay cả mức Advantage $0,032/$0,016 vào/ra cũng khoảng `$7.373`, vượt trần trước compute. Chỉ dùng Kinesis cho metric để tách dashboard khỏi payload ingest.

**Loại Kafka tự quản lý:** có thể rẻ hơn ở tải ổn định nhưng thêm vận hành broker, replication, rebalancing và peak capacity trước khi tải được chứng minh. Benchmark MSK nếu metric stream vượt giả định.

### Quyết định 2 — Iceberg trên object storage với catalog dùng chung

**Chọn:** Iceberg v2 trên S3, đăng ký trong Glue Data Catalog. Một table dùng qua Spark/Trino/Athena/DuckDB, hỗ trợ time travel, hidden partition transforms trên `ts`, và schema/spec evolution mà không cần viết lại ngay mọi file. Glue quản lý catalog; S3 lưu dữ liệu.

**Loại Delta Lake:** phù hợp khi mọi consumer là Spark; nhiều engine ở đây khiến interop quan trọng hơn. Xác minh feature support của từng engine trước production.

**Loại Parquet + Hive partitions:** thiếu transaction log, snapshot isolation, field identity và time travel; analyst phải tự quản lý partition predicates khi layout đổi.

### Quyết định 3 — Partition theo thời gian và bucket tenant, sort theo tenant

**Chọn:** Bronze dùng `hours(ts)` × `bucket(tenant_id, 16)`, file ZSTD 256 MiB, sort `tenant_id, ts`. 5 TiB/ngày tương đương khoảng 225 MiB mỗi bucket/phút nếu phân phối đều. Transform và min/max prune scan tenant/time; dashboard đọc serving view.

**Loại partition theo `tenant_id` trực tiếp:** cardinality cao sinh nhiều partition/file nhỏ và tăng planning cost; bucket giới hạn partition, sort hỗ trợ point lookup.

**Loại partition ngày:** cửa sổ 5 phút phải plan qua nhiều file không liên quan. Hour transform giới hạn thời gian, bucket giới hạn tenant; compaction xử lý lệch phân phối.

### Quyết định 4 — Khử PII trước khi ghi Bronze

**Chọn:** scrubber fail-closed trước cả S3 và Kinesis; redact email/phone/token/ID, thay tenant bằng HMAC token với key trong KMS. Mapping join tùy chọn nằm trong vault break-glass có audit. DLP canary kiểm tra mẫu; analyst không đọc bản rõ.

**Loại mask lúc query:** bản rõ còn trong file, snapshot, export và cache; policy sai có thể để lộ dữ liệu trước khi mask.

**Loại ghi bản rõ rồi sửa sau:** rủi ro bắt đầu từ commit đầu tiên. Scrubber lỗi thì cách ly mã hóa, chặn commit, cảnh báo và xóa theo object/version inventory.

### Quyết định 5 — Retention theo lớp dữ liệu

**Chọn:** payload Bronze và Silver row-level (không có prompt/response) có TTL 7 ngày. Khi hết hạn, chặn reader mới, kết thúc incident session (tối đa 30 phút), expire snapshot rồi sweep file; sau cleanup chỉ còn aggregate. DynamoDB giữ Gold 5 phút trong 48 giờ; Iceberg giữ aggregate ngày một năm. Reader cũ không gia hạn TTL; cleanup phải đáp ứng SLA xóa vật lý.

**Loại archive Bronze lâu hơn:** vượt yêu cầu minimization 7 ngày và thêm retrieval cost; xóa theo lifecycle.

**Loại chỉ đặt S3 lifecycle expiry:** manifest/snapshot có thể còn trỏ tới object đã xóa. Expire snapshot, kiểm tra reader window rồi sweep file unreferenced; lifecycle chỉ là safety net.

### Quyết định 6 — Gold cho dashboard, serving view cho p95 thấp

**Chọn:** streaming tạo Gold aggregates và upsert window mới vào DynamoDB theo `(tenant_id, model, window_start)`. Dashboard đọc key mỗi 5 phút; analyst đọc Gold. Serving view có thể tái dựng, còn version/window ID giúp replay idempotent.

**Loại query Bronze/Silver:** chi tiết không cần cho overview, scan tốn kém và mở rộng quyền đọc nhạy cảm.

**Loại Athena cho mọi refresh:** phù hợp ad hoc hơn hàng triệu key reads; latency dashboard sẽ phụ thuộc scan và số file. Có thể benchmark Gold trực tiếp nếu SLO nới lỏng.

## 4. Sizing và ước tính chi phí tháng

Giá tham chiếu US East: S3 `$0,023/GB-tháng`, Glue `$0,44/DPU-hour`, DynamoDB `$0,625/M writes` và `$0,125/M reads`, Kinesis `$0,08/GB in`, `$0,04/GB out` và `$0,04/stream-hour`. Xác nhận lại theo region bằng AWS Pricing Calculator; đây không phải báo giá.

| Thành phần | Giả định và phép tính | Ước tính/tháng |
|---|---|---:|
| Bronze payload | `5 TiB/ngày × 7 ngày = 35 TiB`; `35 × 1.024 GB × $0,023` (không tính compression) | **$824** |
| Silver row-level | `5 TiB/ngày × 5% × 7 ngày = 1,75 TiB`; `1,75 × 1.024 × $0,023` | **$41** |
| Gold + 48h serving history | 200.000 tenant-model aggregates/ngày × 200 B × 365 ngày = 14,6 GB; 100.000 active combinations × 288 windows/ngày × 200 B × 2 ngày = 11,5 GB; tổng 26,1 GB × $0,023 | **$0,60** |
| S3 requests/metadata reserve | File 256 MiB: Bronze + Silver khoảng 21.504 PUT/ngày, 645.120/tháng; PUT khoảng `$3,23` theo `$0,005/1.000`; thêm GET, Iceberg metadata và lifecycle request reserve | **$25** |
| Kinesis cho metric | 100.000 active tenant-model groups × 288 windows/ngày × 1 KB billable/record = 28,8 GB/ngày; 864 GB/tháng × `($0,08 + $0,04)` + `720 h × $0,04` | **$132** |
| DynamoDB serving | 864 triệu writes/tháng × `$0,625/M` = $540; 86,4 triệu reads/tháng × `$0,125/M` = $10,80; 11,5 GB × `$0,25/GB` ≈ $2,88 (không trừ free tier) | **$554** |
| Glue streaming + compaction | 2 DPU × 720 h × `$0,44` = $633,60; nightly compaction 4 DPU × 0,5 h × 30 × `$0,44` = $26,40 | **$660** |
| Collector capacity allocation | 16 vCPU liên tục × giả định chargeback `$0,10/vCPU-hour` × 720 h; rate này là giả định nội bộ, cần benchmark/định giá lại | **$1.152** |
| **Tổng ước tính** | Storage, request, stream, serving và compute; chưa gồm nhân sự, thuế, egress liên vùng hoặc bản sao DR | **$3.389** |
| **Dự phòng 25%** | Cho tải peak, tỷ lệ nén thấp, scan và compaction vượt mô hình | **$847** |
| **Tổng kèm dự phòng** | So với ngân sách hạ tầng $5.000/tháng | **$4.236** |

Storage 7 ngày ước tính `$824/tháng` trước nén. Tổng phụ thuộc aggregate-at-edge, collector throughput và serving theo key; benchmark tải thật trước khi cam kết SLO. Kịch bản cơ sở có ít nhất 20% headroom trước contingency; DR hoặc retention dài hơn cần tính lại.

## 5. Failure modes và xử lý

| Hỏng lúc production | Phát hiện | Rollback/khắc phục |
|---|---|---|
| Scrubber bỏ sót PII | DLP canary/quarantine counter | Fail closed; chặn ghi, khóa analyst, xóa object/snapshot/export bị ảnh hưởng và rotate key nếu cần; chỉ mở lại sau replay sạch |
| Collector/Kinesis trễ hơn 5 phút | Oldest-event age, iterator age, uncommitted objects, dashboard watermark | Scale writer/consumer, replay checkpoint/Bronze, upsert idempotent; đánh dấu dashboard stale |
| Schema/evolution tạo output sai | Cross-engine contract test, null/unknown-field rate, query canary | Validate trên branch/test table; rollback catalog về snapshot an toàn rồi replay; giữ snapshot tới khi reader kết thúc |
| Snapshot expiry khi query incident còn mở | Query age, snapshot refs, cleaner dry-run | Dừng cleaner, chờ reader timeout (30 phút) rồi chạy lại; không xóa file trong reader horizon |
| Chi phí vượt $5K | Budget alarm 70/85/95%, cost/request, S3 bytes, Glue DPU-hours, Dynamo WRU | Tắt scan/debug và compaction tùy chọn; nếu tải cơ sở vượt cap, xin đổi budget/SLO thay vì âm thầm kéo dài retention |

## 6. MVP trong một tuần

**Ngày 1:** tạo synthetic events/data contract (request ID, timestamp, tenant token, model, token usage, latency, status, payload) và scrubber fail-closed với PII canary.

**Ngày 2:** collector ghi batch 1 phút thành ZSTD Parquet 256 MiB vào Bronze; kiểm tra checksum, manifest và retry event ID trùng.

**Ngày 3:** tạo Iceberg v2 Bronze/Silver trong Glue; kiểm tra schema, snapshot history và hidden partition pruning theo tenant/time.

**Ngày 4:** Kinesis nhận metrics; streaming tạo counts, p50/p95, cost/error rate và ghi idempotent vào Gold/DynamoDB.

**Ngày 5:** benchmark 1/10 tải với peak 4×; chấp nhận khi dashboard p95 < 5 phút, tenant window đúng và không thường xuyên tạo object <64 MiB.

**Ngày 6:** giả lập mốc 7 ngày; chặn reader mới, kết thúc incident session, expire Bronze/Silver snapshots và sweep file quá TTL. Xác nhận chỉ còn Gold aggregates và không có PII canary trong output, quarantine hay serving view.

**Ngày 7:** restore checkpoint/manifest, replay một giờ vào Gold và đối chiếu metrics; chạy Pricing Calculator theo region. MVP cần retry không mất/nhân đôi event, đạt SLO 5 phút, scrub/retention pass và base cost forecast có ít nhất 20% headroom trước contingency.

## 7. Nguồn và giới hạn ước tính

- [AWS S3 pricing](https://aws.amazon.com/s3/pricing/) và [AWS sample pricing table](https://aws.amazon.com/blogs/machine-learning/build-a-serverless-ai-gateway-architecture-with-aws-appsync-events/) — storage, request, retrieval; giá tham chiếu Standard `$0,023/GB-tháng`.
- [Kinesis Data Streams pricing](https://aws.amazon.com/kinesis/data-streams/pricing/) — On-demand Standard và Advantage theo volume vào/ra.
- [AWS Glue pricing](https://aws.amazon.com/glue/pricing/) và [Glue streaming jobs](https://docs.aws.amazon.com/glue/latest/dg/add-job-streaming.html) — `$0,44/DPU-hour`, nguồn stream và tính phí job chạy liên tục.
- [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/) — on-demand request units, lưu trữ và giá tham chiếu đọc/ghi.
- [Apache Iceberg evolution](https://iceberg.apache.org/docs/latest/evolution/) và [Iceberg specification](https://iceberg.apache.org/spec/) — hidden partition, schema/partition evolution và snapshot/file references.

Estimate này cần được hiệu chỉnh theo region, compression, tenant/query mix, record rounding, audit/encryption, replication, compaction và reader duration. Không dùng giá S3 Tables; giả định Iceberg files trên S3 Standard.
