# Architecture brief — Lakehouse cho LLM observability 1B requests/ngày

**Người làm:** Nguyễn Chí Công — 2A202602634
**Phạm vi:** Topic A của Bonus Challenge. Đây là thiết kế giả định để review kiến trúc, không phải mô tả hệ thống đang vận hành.

## 1. Problem statement

API team ghi **1 tỷ request/ngày**, trung bình **5 KB/request**, tức khoảng **5 TB/ngày raw**. Dashboard cost và latency theo tenant phải cập nhật trong 5 phút. Prompt/response đã khử PII cần điều tra incident trong 7 ngày; sau đó chỉ giữ aggregate một năm. Chi phí storage bị giới hạn **5.000 USD/tháng**. Bài toán khó vì cùng một luồng vừa có dữ liệu nhạy cảm, vừa cần truy vấn gần thời gian thực theo `tenant_id`, vừa có nguy cơ tạo ra rất nhiều file và metadata.

Nguyên tắc an toàn là không tạo một bảng analyst có thể đọc chứa clear-text PII. Landing prefix chỉ là vùng đệm kỹ thuật, có bucket policy deny analyst và không được catalog; redactor chạy trước khi có Delta commit trong Bronze. SLO thiết kế là p95 Gold freshness dưới 5 phút, dashboard một tenant/24 giờ p95 dưới 3 giây, và một báo cáo incident luôn chỉ ra được version dữ liệu đã dùng. Giải pháp dùng S3 + Delta Lake + Glue Catalog/Athena. Chi phí là ước lượng cho us-east-1, 30 ngày và cần xác nhận bằng Pricing Calculator trước khi mua.

## 2. Kiến trúc đề xuất

```text
SDK/API gateways (1B req/day, 5 TB/day)
          |
          v
Kinesis + isolated landing (SSE-KMS; deny analyst read)
          |  DLP/redactor + deterministic token service + quarantine
          v
BRONZE Delta /events_redacted
  - 512 MB files; date/hour partition; 7-day retention; CDF
          |                         \
          | streaming MERGE           \ unknown PII/schema
          v                           v
SILVER Delta /request_facts       Quarantine, alert, CDF replay
  - typed facts/token only; cluster by tenant_id
          |
          | 5-minute materialization
          v
GOLD Delta /tenant_5m_metrics ---> Athena/BI dashboard
  - cost, p50/p95 latency, errors; 365-day aggregate retention
          |
          +--> OPTIMIZE, checkpoint, expiry/VACUUM, S3 IA lifecycle

Glue Catalog + Lake Formation permissions + CloudTrail audit + cost alarms
```

Sơ đồ áp dụng các concept Day18 thành quyết định vận hành: (1) medallion Bronze→Silver→Gold, (2) Delta ACID/CDF/time travel để replay và rollback, (3) partition + clustering `tenant_id` để pruning hot path, (4) compaction/checkpoint/retention để trị small files, (5) tokenization và catalog governance trước khi analyst đọc, và (6) lifecycle S3 cho FinOps.

## 3. Sáu quyết định và alternatives đã loại

### 3.1 Table format

Tôi chọn **Delta Lake trên S3** cho cả ba layer. Transaction log, snapshot, CDF và `RESTORE` phục vụ replay micro-batch, audit version của dashboard, và rollback sau lỗi. Silver/Gold chỉ advance khi data quality pass, nên BI không đọc nửa batch.

Tôi loại **Parquet thuần** vì writer đồng thời không có atomic snapshot; dashboard có thể đọc tập file không nhất quán. Tôi loại **Iceberg** không phải vì nó yếu, mà vì đội này đã có Delta/CDF và requirement replay theo commit sẽ ít rủi ro hơn. Iceberg sẽ được đánh giá lại nếu Trino/Snowflake multi-engine trở thành đường query chính.

### 3.2 Partition, cluster và file size

Tôi chọn partition `event_date,event_hour` cho Bronze/Silver; Gold partition theo ngày và Z-ORDER/cluster `tenant_id,event_ts`. File mục tiêu 512 MB và OPTIMIZE partition đóng sau 2 giờ. Dashboard có tenant + time range nên chỉ mở phần nhỏ file cần thiết.

Tôi loại partition trực tiếp **theo tenant** vì cardinality cao gây small partitions và metadata bùng nổ. Tôi loại partition **chỉ theo ngày** vì query một tenant/24 giờ vẫn mở quá nhiều file. Tôi loại file 32 MB: ingest trông nhanh nhưng list, planning và compaction đắt theo số file.

### 3.3 PII và governance

Tôi chọn DLP/redactor streaming với **deterministic tokenization**: HMAC của PII đã chuẩn hóa, secret trong KMS/HSM. Cùng subject cho cùng token để có thể join/debug; analyst chỉ thấy token hoặc nội dung redacted. Landing chỉ cấp service role, Lake Formation cấp quyền theo table/column cho Silver/Gold, còn CloudTrail ghi audit read.

Tôi loại **mask PII ở BI layer** vì clear-text vẫn tồn tại trong Bronze mà role có quyền table có thể đọc. Tôi loại **hash không secret** vì email/số điện thoại dễ dictionary attack và không hỗ trợ rotation. Tôi cũng loại encryption-at-rest đơn thuần: nó không ngăn một principal hợp lệ đọc PII.

### 3.4 Retention và maintenance

Tôi chọn Bronze redacted giữ 7 ngày trên S3 Standard; Silver facts và Gold aggregates giữ 365 ngày, chuyển Standard-IA sau 30 ngày. Weekly job expire snapshot theo policy, `VACUUM` sau cửa sổ rollback 8 ngày, checkpoint log và orphan sweep sau khi xác minh active reference. Job maintenance phải xuất file-count, bytes reclaimed, snapshot count trước/sau.

Tôi loại giữ **toàn raw một năm**: `5 TB/day × 365 = 1.825 TB`, phá budget trước compute. Tôi loại Glacier cho Gold 90 ngày đầu vì dashboard cần giây/phút, còn Glacier Flexible Retrieval có thể cần hàng giờ. Tôi loại `VACUUM 0 HOURS` vì phá cửa sổ time travel và điều tra incident.

### 3.5 Ingestion và serving

Tôi chọn Kinesis + Glue/Spark streaming, ghi idempotent theo `request_id`, watermark event time 30 phút và `MERGE` cho late event. Gold materialize mỗi 5 phút; dashboard chỉ đọc Gold qua Athena workgroup có bytes-scanned cap. Incident query đi qua Silver bằng role riêng.

Tôi loại microservice ghi trực tiếp một event/một S3 file vì sẽ tạo hàng triệu small files và không có commit batch. Tôi loại ELT ban đêm vì không đạt 5 phút. Tôi loại dashboard đọc Silver/Bronze trực tiếp vì scan cost/latency khó dự đoán và tăng bề mặt lộ prompt detail.

### 3.6 Catalog và data contract

Tôi chọn **Glue Catalog** làm catalog trung tâm; data contract (schema, required fields, classification) version trong Git và kiểm ở CI trước producer release. Một catalog giúp audit/lineage tập trung.

Tôi loại Hive metastore tự vận hành vì HA, backup và permission synchronization là burden không giúp SLO. Tôi loại catalog riêng từng team vì lineage/audit phân mảnh và cấp quyền `tenant_id` dễ lệch. Tôi không cho nhiều engine cùng ghi Delta log từ ngày đầu; interop/migration là quyết định riêng có test concurrency.

## 4. Chi phí và guardrail FinOps

Tôi dùng TB thập phân. Bronze 7 ngày là `5 TB/day × 7 = 35 TB`. Silver bỏ prompt/response, giữ facts đã nén bằng `3% × 5 TB/day × 365 = 54,75 TB`. Gold aggregate là `5 GB/day × 365 = 1,825 TB`. Tôi thêm 20% cho active Delta files, snapshot overlap ngắn hạn và metadata.

| Hạng mục | Phép tính | USD/tháng |
|---|---:|---:|
| Bronze S3 Standard | `35 TB × $23/TB-month` | $805 |
| Silver + Gold Standard-IA | `56,575 TB × $12,50` | $707 |
| Version/metadata headroom | `20% × ($805 + $707)` | $302 |
| PUT/GET, inventory, lifecycle requests | envelope | $250 |
| **Storage subtotal** |  | **$2.064** |
| Streaming redaction/transform | `4 DPU × 720h × $0,44` | $1.267 |
| Daily compaction | `10 DPU × 2h/day × 30 × $0,44` | $264 |
| Quality, expiry, checkpoint | `2 DPU × 1h/day × 30 × $0,44` | $26 |
| Athena Gold queries | `10 TB × $5/TB` | $50 |
| **Operating estimate** | storage + compute/query | **$3.671** |

Storage-only $2.064 thấp hơn hard cap $5.000, buffer $2.936. Tham chiếu giá list phải kiểm lại theo region tại [S3 Pricing](https://aws.amazon.com/s3/pricing/) và [AWS Glue Pricing](https://aws.amazon.com/glue/pricing/); Glue minh họa $0,44/DPU-hour. Cost alarm đặt ở 60%, 80%, 95% storage cap; Athena workgroup chặn query quét quá budget và chi phí được chargeback theo tenant. Rủi ro lớn là giả định nén Silver, CPU redaction và tần suất query. Benchmark MVP phải chứng minh 4 DPU xử lý trung bình 58 MB/s; nếu cần autoscale compute thì storage cap vẫn không thay đổi.

## 5. Failure modes lúc 3 giờ sáng

| Failure | Detection | Cô lập và rollback |
|---|---|---|
| Redactor deploy lỗi, PII clear-text lọt vào Bronze | DLP canary và sampling scan sau write vượt baseline | Stop writer, revoke access, quarantine theo `batch_id`, `RESTORE` Delta về version trước, rồi replay landing cô lập bằng redactor đã sửa. Audit mọi read attempt. |
| Producer đổi kiểu `latency_ms`, Silver/Gold sai | Contract CI, metric quarantine rows và Gold freshness alert | Không auto-merge breaking schema. Giữ Gold ở snapshot tốt, quarantine schema mới, phát hành transform tương thích và replay CDF từ version lỗi. Đây là schema evolution có kiểm soát. |
| OPTIMIZE/VACUUM retention sai, xóa file phục vụ incident | Dry-run bytes, active-file count, snapshot-age policy alert | Disable maintenance, `RESTORE` logical table nếu metadata còn; khôi phục object backup trong cửa sổ 8 ngày rồi rebuild Silver/Gold từ Bronze. Runbook cấm VACUUM dưới rollback window. |
| Tenant hot làm p95 dashboard vượt 3 giây | Per-tenant scan bytes, file-skew percentile và Athena p95 | Serve Gold window thành công gần nhất, compact partition nóng; nếu layout sai, ghi mới theo time + hash bucket, backfill/reconcile rồi chuyển view. |

## 6. MVP một tuần và chứng minh feasibility

Tôi không xây 1B request/ngày trong tuần đầu. Slice là **10 triệu synthetic events/ngày**, 100 tenant, cùng schema và skew mô phỏng production: stream simulator, redactor/token, Delta Bronze→Silver→Gold, dashboard query, compact/replay job.

| Ngày | Deliverable | Tiêu chí nghiệm thu |
|---|---|---|
| 1 | IaC tối thiểu, KMS roles, schema contract | Analyst bị deny với landing; CI từ chối breaking schema. |
| 2–3 | Redactor + Bronze/Silver CDF | 100% PII test thành token/redacted; cùng input ra cùng token; unknown vào quarantine. |
| 4 | Gold 5-minute metrics + Athena | Tenant/24h p95 <3 giây, không scan Bronze. |
| 5 | Late event và replay | Event trong watermark merge đúng; replay `batch_id` không double-count. |
| 6 | Compaction/checkpoint/retention dry-run | File count giảm ≥10×; incident snapshot chưa bị xóa. |
| 7 | Load test, chaos drill, cost report | 58 MB/s benchmark, freshness <5 phút, redactor failure được restore/replay. |

Mechanism khó nhất là redaction/tokenization trước reader access mà vẫn replay idempotent. Test sẽ gieo email, phone và biến thể Unicode vào synthetic events; truy vấn Bronze/Silver/Gold không được tìm thấy clear-text. Sau đó cố ý cho redactor fail một `batch_id`, kiểm batch quarantine, sửa pipeline và replay bằng CDF; Gold vẫn không double-count. Không qua test này thì không mở dashboard dù latency/cost tốt.

## 7. Kết luận và phạm vi dùng AI

Thiết kế này đánh đổi multi-engine flexibility lấy auditability, latency ổn định và chi phí đo được: Delta là backbone transaction/replay, Gold là contract dashboard duy nhất, PII bị loại trước reader access, còn compaction/expiry/cost alarm là first-class jobs.

AI được dùng để hỗ trợ tổ chức bản nháp, rà rubric và diễn giải trade-off; tôi tự chọn topic, kiểm phép tính, điều chỉnh quyết định và chịu trách nhiệm về nội dung cuối cùng.
