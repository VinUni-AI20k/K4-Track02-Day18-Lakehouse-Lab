# Architecture Brief — LLM Observability 1B request/ngày

> **Tác giả:** Đinh Ngọc Đức — 2A202602935
>
> **Topic:** A — LLM observability ở quy mô 1B requests/ngày
>
> **Phạm vi:** quyết định kiến trúc cho data plane; không phải báo giá hay hồ sơ tuân thủ pháp lý.

## 1. Problem statement

Nền tảng phục vụ 1 tỷ request LLM mỗi ngày, trung bình 5 KB/request, tương đương
5 TB raw/ngày và 11.574 request/s trung bình. Hệ thống phải chịu peak 5×
(xấp xỉ 58.000 request/s), cập nhật dashboard cost/latency theo tenant trong
5 phút, giữ prompt/response đầy đủ đã token hóa trong 7 ngày và chỉ giữ
aggregate trong 365 ngày. PII không được xuất hiện trong bảng mà analyst có thể
đọc. Incident responder cần lọc theo tenant và thời gian mà không scan toàn bộ
tuần dữ liệu. Storage có cap cứng 5.000 USD/tháng; pipeline phải cho phép replay,
dedup, rollback aggregate sai và xóa vật lý sau retention mà không làm hỏng
reader đang chạy. Điểm khó không phải ghi được 5 TB/ngày mà là đồng thời giữ
freshness, privacy, khả năng audit và chi phí ổn định khi streaming tạo small
files liên tục.

### Ràng buộc và giả định có thể kiểm tra

| Mục | Giá trị thiết kế |
|---|---:|
| Ingest trung bình / peak | 11.574 / 58.000 events/s |
| Raw payload | 5 TB/ngày; 5 KB/request |
| Dashboard freshness | ≤ 5 phút; query Gold p95 mục tiêu ≤ 2 giây |
| Incident data | 7 ngày logic; 8 ngày vật lý gồm 24 giờ reader-safety grace |
| Aggregate | 5 phút × tenant × model; giữ 365 ngày |
| Tenant | 100.000 active; trung bình 2 model active/tenant/window |
| Silver projected row | 0,5 KB/request trước compression |
| Gold projected row | 160 B/tenant-model-window |
| Compression planning | 2,5×; stress case chỉ 1,25× |
| File target sau compaction | 256–512 MB |
| Storage budget | ≤ 5.000 USD/tháng |

TB trong phép tính workload là số thập phân để bám đề bài. Giá cloud là planning
rate tại thời điểm viết, chưa gồm thuế, egress và support; trước production phải
chạy lại pricing calculator theo region.

## 2. Kiến trúc đề xuất

~~~mermaid
flowchart LR
    subgraph client ["Producers and readers"]
        apiFleet["Model API fleet"]
        dashboard["Tenant dashboards"]
        responder["Incident responder"]
    end
    subgraph gateway ["Access layer"]
        ingestGateway["Authenticated ingest gateway"]
        sqlGateway["SQL and policy gateway"]
    end
    subgraph service ["Lakehouse services"]
        tokenizer["PII tokenizer and contract validator"]
        bronzeWriter["Idempotent Bronze writer"]
        silverJob["Silver parse and dedup stream"]
        goldJob["Five-minute Gold aggregator"]
        queryService["SQL warehouse"]
        maintenance["OPTIMIZE, checkpoint, VACUUM and orphan sweep"]
    end
    subgraph async ["Streaming buffer"]
        kafka["Encrypted Kafka, two-hour replay"]
    end
    subgraph datastore ["Governed storage"]
        tokenVault["Restricted token vault"]
        bronze["Delta Bronze, full tokenized body, seven days"]
        silver["Delta Silver, metrics and body pointer, seven days"]
        gold["Delta Gold, tenant-model windows, 365 days"]
        catalog["Catalog, RBAC, lineage and audit"]
    end
    subgraph external ["Security and operations"]
        kms["KMS and secret manager"]
        alerts["Metrics and paging"]
    end

    apiFleet -->|"Batched HTTPS"| ingestGateway
    ingestGateway -->|"Validated events"| tokenizer
    tokenizer -->|"Deterministic tokens"| tokenVault
    tokenizer -.->|"KMS: encrypt"| kms
    tokenizer -.->|"Publish tokenized"| kafka
    kafka -.->|"Consume and replay"| bronzeWriter
    bronzeWriter -->|"ACID append"| bronze
    bronze -->|"CDF and event time"| silverJob
    silverJob -->|"MERGE request_id"| silver
    silver -->|"Incremental windows"| goldJob
    goldJob -->|"MERGE five-minute metrics"| gold
    goldJob -->|"Commit metadata"| catalog
    dashboard -->|"Tenant query"| sqlGateway
    responder -->|"Restricted incident query"| sqlGateway
    sqlGateway -->|"Authorized SQL"| queryService
    queryService -->|"Dashboard scans"| gold
    queryService -->|"Incident lookup"| bronze
    queryService -->|"Policy and lineage"| catalog
    maintenance -->|"Compact and expire"| bronze
    maintenance -->|"Compact and expire"| silver
    maintenance -->|"Checkpoint and validate"| gold
    maintenance -.->|"SLO and cost alerts"| alerts
~~~

Luồng chính là tokenization trước durable lake landing, sau đó
Bronze → Silver → Gold. Dashboard chỉ đọc Gold; quyền incident riêng mới đọc
payload Bronze. Catalog là control plane cho RBAC, ownership, schema và audit,
không nằm trên đường ghi payload.

### Data contract và concept Day18 được áp dụng

| Zone | Nội dung và layout | Day18 concept được dùng |
|---|---|---|
| Bronze | **request_id**, **event_ts**, **tenant_token**, model, prompt/response đã token hóa, **redaction_version**, raw hash; partition **event_date/hour** | schema enforcement, ACID append, time travel, retention |
| Silver | Một dòng hợp lệ/request; typed token counts, latency, status, body pointer; dedup bằng MERGE trên **request_id** | medallion, MERGE/idempotency, CDF, late-data handling |
| Gold | 5-minute tenant-model windows: requests, tokens, cost, p50/p95, error rate | incremental aggregate, Gold serving, version pin cho dashboard release |
| Physical layout | 256–512 MB/file; Z-order **tenant_token, event_ts**; checkpoint định kỳ | compaction, clustering/file pruning, transaction-log checkpoint |
| Lifecycle | Bronze/Silver 7 ngày logic + 24 giờ grace; Gold 365 ngày; VACUUM và orphan sweep tách biệt | snapshot retention, physical deletion, reader safety, FinOps |
| Governance | token vault tách biệt; catalog RBAC/lineage; audit mọi lần detokenize | catalog control plane, provenance, least privilege |

## 3. Bảy quyết định có alternatives bị loại

### D1 — Table format: chọn Delta Lake

**Chọn Delta Lake** vì workload là append streaming nhưng vẫn cần MERGE để
dedup/late correction, CDF để cập nhật Gold, time travel/RESTORE khi công thức
cost sai, và OPTIMIZE/Z-order cho tenant lookup. **Loại raw Parquet** vì không có
transaction log, schema enforcement hay snapshot nhất quán; retry có thể tạo
duplicate mà reader thấy ngay. **Loại Iceberg cho phiên bản đầu** dù hidden
partitioning và multi-engine rất tốt, vì team này ưu tiên đường Delta
MERGE/CDF/Z-order đã vận hành; Iceberg sẽ được xem lại nếu Trino/Flink
interoperability trở thành hard requirement. Đổi lại, quyết định này buộc catalog
và engine phải được kiểm thử tương thích, không coi “file Parquet” là đủ.

### D2 — Ingestion: chọn Kafka provisioned + stream processor

**Chọn Kafka provisioned với hai giờ replay** và consumer checkpointed; stream
processor scale theo peak 58K events/s. Nó tách backpressure khỏi API, cho replay
khi writer lỗi và giữ dashboard trong cửa sổ 5 phút. **Loại API ghi thẳng object
storage** vì request nhỏ tạo hàng triệu file, retry khó idempotent và redaction
failure lan thẳng vào lake. **Loại hourly batch** vì vi phạm freshness 5 phút và
tạo blast radius một giờ. Kafka không phải system of record: retention ngắn,
Bronze commit thành công mới advance consumer offset.

### D3 — PII: chọn tokenize trước Kafka và Bronze

**Chọn validator/tokenizer đồng bộ trước publish**, dùng HMAC token ổn định cho
tenant/subject và vault mã hóa cho trường thật sự cần detokenize. Mọi row ghi
**redaction_version** và hash để audit/replay. **Loại redact ở Silver** vì raw PII
đã nằm trong Bronze và có thể bị analyst/time travel đọc trước khi job chạy.
**Loại chỉ mã hóa bucket** vì quyền đọc object hoặc query engine vẫn giải mã toàn
payload, không phải field-level minimization. Nếu tokenizer không chắc chắn,
event vào quarantine service-only và không được publish; “best effort redact”
không được phép.

### D4 — Medallion: chọn full body một lần, metrics riêng

**Chọn Bronze giữ full tokenized prompt/response**, Silver giữ metrics chuẩn hóa
cùng pointer/request ID, Gold giữ aggregate. Cách này tránh nhân đôi 5 KB body
trong mọi zone nhưng vẫn replay được trong 7 ngày. **Loại copy full body sang
Silver** vì gần gấp đôi 16 TB hot footprint mà dashboard không dùng. **Loại một
bảng duy nhất** vì dashboard phải scan row rộng, governance không tách được
incident reader và schema evolution của metrics đụng payload. Body pointer chỉ
hợp lệ trong retention; sau ngày 7, Gold là nguồn duy nhất được cam kết.

### D5 — Partition và clustering: chọn giờ + Z-order tenant/time

**Chọn partition low-cardinality event_date/hour và Z-order
tenant_token/event_ts**, target 512 MB. Time predicate prune partition,
min/max stats prune file cho tenant. **Loại partition trực tiếp theo tenant**
vì 100K tenant × 24 giờ tạo metadata/small-file explosion và commit contention.
**Loại chỉ partition theo ngày, không clustering** vì một tenant incident phải
chạm hàng nghìn file trong 2 TB/ngày. Acceptance gate là point query prune
ít nhất 10× và không partition nào có median file dưới 128 MB sau compaction.

### D6 — Query serving: chọn Gold-first, Bronze restricted

**Chọn SQL warehouse đọc Gold cho dashboard**; stream job MERGE window đã đóng
và sửa window muộn trong 24 giờ. Incident responder qua role riêng mới đọc
Bronze theo tenant/time. **Loại dashboard scan Silver/Bronze** vì 1B rows/ngày
làm latency và compute tỷ lệ với raw volume. **Loại đồng bộ mọi metric sang một
OLTP database** vì tạo system-of-record thứ hai và lifecycle skew khi
correction/delete không truyền đủ. Cache dashboard tối đa 60 giây, nhưng
freshness được đo từ source event đến Gold commit, không từ cache hit.

### D7 — Lifecycle và maintenance: chọn policy có grace, không retention 0

**Chọn logical retention 7 ngày, 24 giờ grace trước VACUUM, hourly compaction,
checkpoint thường xuyên và daily orphan sweep**. Gold giữ 365 ngày; job ghi
metric bytes/files/snapshots trước–sau. **Loại VACUUM retention 0** vì reader
đang pin version cũ có thể mất file giữa query. **Loại chỉ đặt object lifecycle
rule** vì rule không hiểu transaction log và có thể xóa file còn được snapshot
tham chiếu; ngược lại, snapshot expiry chỉ bỏ tham chiếu chưa bảo đảm xóa vật
lý. Mỗi ngày phải đối soát live metadata với object inventory.

## 4. Ước lượng storage và compute

### Storage steady-state

Planning rate object storage là **23,50 USD/TB-tháng**, xấp xỉ mức Standard
US-East; giá thật phụ thuộc region/storage class theo
[AWS S3 pricing](https://aws.amazon.com/s3/pricing/). Kafka broker storage dùng
**0,10 USD/GB-tháng**, cùng cách tính trong
[AWS MSK pricing](https://aws.amazon.com/msk/pricing/).

| Thành phần | Phép tính | Footprint | USD/tháng |
|---|---|---:|---:|
| Bronze | 5 TB/ngày ÷ 2,5 × 8 ngày vật lý | 16,00 TB | 376,00 |
| Silver metrics | 0,5 TB/ngày ÷ 2,5 × 8 ngày | 1,60 TB | 37,60 |
| Gold | 200K groups/window × 288 × 160 B × 365 | 3,36 TB | 78,96 |
| Delta log/checkpoint/headroom | 15% × (16 + 1,6 + 3,36) | 3,14 TB | 73,79 |
| Token vault | 0,1 TB/ngày × 8 ngày × 100 USD/TB-tháng | 0,80 TB | 80,00 |
| Kafka replay | 5 TB/ngày × 2/24 × RF=3 × 102,40 USD/TB | 1,25 TB | 128,00 |
| **Tổng storage** | object 24,10 TB + vault + Kafka | **26,15 TB** | **774,35** |

Storage dùng **15,5% cap 5.000 USD/tháng**. Combined stress case gồm compression
chỉ 1,25× và token-vault volume tăng 2×: object footprint lên khoảng 44,34 TB;
object cost 1.041,99 USD, vault 160 USD và Kafka 128 USD, tổng khoảng
**1.329,99 USD/tháng (26,6% cap)**.
Cap vì vậy không phụ thuộc một giả định compression lạc quan.

Sau compaction, ước lượng object data là:

- Bronze: 2.000 GB/ngày ÷ 0,512 GB × 8 ≈ 31.250 file.
- Silver: 200 GB/ngày ÷ 0,512 GB × 8 ≈ 3.125 file.
- Gold: 9,216 GB/ngày ÷ 0,512 GB × 365 ≈ 6.570 file.

Khoảng 41K data file là quy mô catalog quản lý được; cảnh báo mở khi file count
cao hơn dự báo 2× hoặc p50 file size dưới 128 MB.

### Compute và service planning

| Thành phần | Phép tính planning | USD/tháng |
|---|---|---:|
| Kafka brokers | 12 × 0,204 USD/giờ × 720 giờ | 1.762,56 |
| Tokenize + stream jobs | 30 worker-equivalent × 0,34 USD/giờ × 720 | 7.344,00 |
| Compaction/OPTIMIZE | 66 TB/tháng × 5 USD/TB processed | 330,00 |
| Query warehouse | 16 vCPU × 12 giờ/ngày × 30 × 0,06 USD/vCPU-giờ | 345,60 |
| Catalog, audit, monitoring allowance | fixed planning allowance | 500,00 |
| **Tổng compute/service** |  | **10.282,16** |
| **Storage + compute** | 10.282,16 + 774,35 | **11.056,51** |

Mức 0,204 USD/broker-giờ lấy từ ví dụ **kafka.m7g.large** trên trang MSK; các
worker/warehouse/maintenance rates là giả định nội bộ để so sánh, không phải
báo giá vendor. Network, KMS request, support và tax chưa tính. Trước go-live,
benchmark phải chứng minh 30 worker-equivalent xử lý peak 290 MB/s; nếu không,
compute forecast được thay bằng kết quả benchmark, còn storage cap vẫn kiểm
tra độc lập.

## 5. Failure modes và rollback

| Failure lúc 03:00 | Detect cụ thể | Containment và rollback |
|---|---|---|
| Redaction rule mới bỏ sót phone/email | DLP canary ở mỗi batch; scan token-pattern trên Bronze; alert nếu raw-canary > 0 | Dừng publish/offset, khóa partition bằng catalog policy, sửa **redaction_version**, replay Kafka; VACUUM bản lỗi chỉ sau khi xác nhận không còn reader |
| Công thức cost hoặc schema Gold sai | Reconcile tổng token/cost Gold với Silver mỗi 5 phút; schema contract CI; chênh > 0,1% page | Dừng dashboard version mới, time travel/RESTORE Gold về version tốt, sửa job rồi replay CDF từ version đã pin |
| Duplicate hoặc late event làm double-count | Uniqueness **request_id**, watermark lag histogram, source-vs-Silver count | MERGE chỉ nhận event mới hơn; replay checkpoint; recompute 24 giờ Gold windows, không sửa thủ công |
| Streaming tạo small files, tenant query chậm | p50 file size, file count/partition, files-touched point query, catalog planning time | Scale compaction, tăng writer buffer, OPTIMIZE/Z-order partition bị ảnh hưởng; rollback target size nếu job tạo file quá lớn |
| VACUUM/lifecycle xóa file reader cũ còn dùng | Vacuum dry-run diff, active-reader watermark, restore drill; missing-file error page | Ngừng vacuum, phục hồi object version/backup và RESTORE table; tăng grace vượt longest query + stream lag; không dùng retention 0 |
| Catalog outage hoặc commit conflict | commit latency/error rate, Kafka consumer lag, catalog health check | Giữ event tokenized trong Kafka, pause offset commit, fail closed cho query nhạy cảm; restore catalog backup rồi resume idempotent writer |

Ba failure đầu kiểm chứng trực tiếp các concept Day18: schema enforcement +
time travel, MERGE/idempotency và compaction/clustering. Failure VACUUM phân biệt
“không còn tham chiếu” với “đã xóa vật lý”.

## 6. MVP một tuần

MVP dùng **10 triệu event giả lập (~50 GB raw, 1% một ngày)**, 100 tenant và
ba model. Không build UI đẹp, multi-region hay detokenization workflow hoàn
chỉnh; mục tiêu là chứng minh data contract và failure recovery.

| Ngày | Slice bàn giao |
|---:|---|
| 1 | Chốt schema, generator, seeded PII corpus, request IDs và cost table; tạo catalog/table policies |
| 2 | Ingest gateway + deterministic tokenizer + Kafka; test fail-closed và replay |
| 3 | Bronze/Silver Delta, schema enforcement, dedup MERGE, CDF; lưu metric freshness |
| 4 | Gold 5-minute aggregate, dashboard SQL, partition hour và Z-order tenant/time |
| 5 | Compaction, checkpoint, retention dry-run, orphan sweep; inject bad Gold rồi RESTORE |
| 6 | Load test 5× peak tương đương, đo files touched, p95/freshness và cập nhật cost model |
| 7 | Failure drill, runbook, evidence, decision review và go/no-go |

### Acceptance criteria

1. **Privacy:** 10.000 seeded PII cases có recall 100%; không raw canary nào xuất
   hiện trong Bronze/Silver/Gold. Tokenizer unavailable thì ingest fail closed.
2. **Correctness:** chạy lại cùng input hai lần không đổi row count, token total,
   cost hoặc error rate; Silver có đúng một **request_id**.
3. **Freshness:** 99% event vào Gold trong 5 phút; late event trong 24 giờ sửa
   đúng window mà không double-count.
4. **Performance:** tenant point query prune ≥ 10× file; Gold query p95 ≤ 2 giây
   trên test warehouse.
5. **Maintenance:** compaction giảm ≥ 10× file và p50 file size đạt
   256–512 MB; checkpoint đọc được; orphan sweep không đụng live file.
6. **Recovery:** inject công thức cost sai, phát hiện qua reconciliation và
   RESTORE version tốt trong ≤ 15 phút; replay tạo lại Gold đúng.
7. **FinOps:** báo cáo tự tính footprint từ bytes thực tế; base và stress case
   đều dưới 5.000 USD storage/tháng.

Cơ chế khó nhất là **tokenize-before-Bronze nhưng vẫn replay idempotent**. Test
nghiệm thu ngắt tokenizer giữa batch, xác nhận không có offset nào được commit
và không có raw row trong lake; sau khi khôi phục, replay phải cho cùng hash,
token và aggregate như lần chạy không lỗi.

## 7. Giới hạn và nguồn

- Đây là single-region MVP. Multi-region chỉ thêm sau khi đo RPO/RTO; không
  dual-write hai table vì commit ordering khó chứng minh.
- Tokenization giảm lộ PII nhưng không tự tạo quyền sử dụng dữ liệu; retention,
  access purpose và incident approval vẫn cần policy/legal review.
- Dashboard aggregate không thể thay thế prompt/response sau ngày 7; đó là
  lựa chọn có chủ đích để giữ cap.
- PoC code không thêm vì bonus chấm architecture document; tuần MVP đã nêu
  mechanism khó nhất, test và acceptance gate.

Nguồn đối chiếu:

- [Bonus Challenge của lab](../../docs/bonus/BONUS-CHALLENGE.md)
- [Day18 checkpoints](../../docs/CHECKPOINTS.md)
- [AWS S3 pricing](https://aws.amazon.com/s3/pricing/)
- [AWS MSK pricing](https://aws.amazon.com/msk/pricing/)
- [Delta Lake optimization](https://docs.delta.io/latest/optimizations-oss.html)
- [Delta Lake utility commands và VACUUM](https://docs.delta.io/latest/delta-utility.html)
