# Architecture brief — LLM observability 1B requests/ngày (Topic A)

**Tác giả:** Đoàn Tuấn Long · 2A202602609 · K4-Track02-Day18 · bài cá nhân
**PoC:** [`poc/poc_pii_retention.ipynb`](poc/poc_pii_retention.ipynb) (bản `.py` chạy được từ clean checkout)

> Mọi đơn giá cloud trong bài là **giả định** lấy theo bảng giá công khai AWS us-east-1 (S3, MSK, EC2)
> mà tôi dùng làm tham chiếu, chưa xác minh lại cho tháng 10/2026. Phép tính được viết đủ để thay
> đơn giá khác vào. Tỷ lệ nén là giả định, sẽ được đo lại trong MVP (tiêu chí A5).

---

## 1. Problem statement

Một team cung cấp foundation-model API cần log mọi request/response: **1B request/ngày × ~5 KB =
5 TB/ngày raw** (trung bình 11 574 req/s ≈ 58 MB/s; giả định peak 3× ≈ 35 K req/s). Yêu cầu:
(1) dashboard cost & latency **theo tenant**, refresh mỗi **5 phút**; (2) prompt/response đầy đủ
giữ **7 ngày** cho incident review, sau đó chỉ còn aggregates trong **1 năm**; (3) **PII phải được
redact trước khi bất kỳ ai đọc**; (4) tổng chi phí storage **≤ \$5 K/tháng**.

Khó vì bốn ràng buộc kéo ngược nhau. Freshness 5 phút đòi commit thường xuyên → small files
(NB2/NB6). "Giữ 7 ngày" là yêu cầu *xoá vật lý*, trong khi table format giữ file cũ cho time travel
(NB3/NB6: delete và expiry đều không tự xoá byte). PII nằm *bên trong* free text nên không thể che
bằng column masking. Còn nếu giữ raw 1 năm thì riêng storage đã là 1.8 PB ≈ \$38 K/tháng, gấp 7.7 lần
budget. Giả định thêm: 10 000 tenant, 3–5 model, tenant lớn nhất chiếm ~30% traffic.

## 2. Architecture

```
  API gateways (1B req/day, peak 35K req/s)
        │  raw event JSON (contains PII)
        ▼
  Kafka / MSK  ── retention 24h, ACL: only the ingest principal, encrypted at rest      [C7 security]
        │
        ▼
  Flink ingest job ─────────────────────────────────────────────────────────────────────────────┐
   1. PII tokenizer: keyed HMAC-SHA256 on e-mail/phone/ID + NER on free text  [C7: PII at Bronze]│
      originals ──► VAULT table (encrypted, 7d TTL, break-glass role, every read audited)        │
   2. Iceberg sink, commit every 60 s (exactly-once via Flink checkpoint)        [C2 ACID commit] │
   3. 5-min tumbling window per (tenant, model), watermark 10 min → Gold provisional             │
        │                         │                                     │
        ▼                         ▼                                     ▼
  BRONZE llm_events_raw     SILVER llm_calls                      GOLD tenant_5min / tenant_daily
  redacted prompt+response  dedup by request_id, typed,           calls, errors, tokens, cost_usd,
  partition day(ts)         NO text, cost_usd                     p50/p95/p99 (KLL sketch)
  sort ts                   partition day(ts), sort (tenant,ts)   partition month(bucket),
  TTL 7 days                TTL 7 days                            sort tenant, TTL 365 days
  ~1.23 TB/day              ~50 GB/day                            ~0.9 GB/day           [C1 medallion]
        │                         │                                     │
        └──────── Iceberg REST catalog (Apache Polaris): one pointer per table,    [C3 catalog]
                  table-scoped credential vending: Bronze → role incident_reviewer only
                          │                                         │
  Maintenance (Spark, nightly + hourly)                     Query path
   hourly : compact Silver/Gold, sort by tenant  [C5 clustering]   Trino (+ local SSD file cache)
   01:00  : DELETE day < today-7 (whole-file drop)  [C4 hidden partition day(ts)]
   13:00  : expire snapshots + orphan sweep + rewrite_manifests  [C6 maintenance, time-travel window]
   03:00  : Gold reconciliation for day D-1 from Silver (late data) ──► Gold is_final = true
                                                                    dashboards: Gold only, WHERE tenant_id = ?
                                                                    incident review: Bronze by ts range
  FinOps [C8]: S3 Standard only (no IA for <30-day data); alerts on avg file size & file count
```

Day18 concepts áp dụng vào lựa chọn cụ thể: **C1** medallion với TTL khác nhau theo lớp; **C2** ACID
commit 60 s của Iceberg (reader không bao giờ thấy file nửa vời); **C3** catalog làm control plane
và ranh giới phân quyền; **C4** hidden partitioning `day(ts)` để retention khớp ranh giới file;
**C5** clustering theo tenant cho hot path; **C6** 4 job maintenance + checkpoint/manifest rewrite;
**C7** tokenization tại Bronze; **C8** FinOps tiering.

## 3. Quyết định chính và alternatives bị loại

**D1 — Table format: chọn Apache Iceberg v2.**
- Loại **Delta Lake**. Delta làm tốt ACID và time travel (NB1/NB3), nhưng hai thứ tôi cần nhất lại
  là điểm mạnh của Iceberg. Thứ nhất, *hidden partitioning*: với Delta, ngày phải là một cột sinh ra
  (generated column) hoặc cột ghi tay, và NB4 đã cho thấy lỗi `CAST(ts AS DATE)` theo múi giờ máy
  tạo ra 8 "ngày" lệch 7 giờ. Với `day(ts)`, transform nằm trong spec của bảng, mọi engine suy ra
  giống nhau. Thứ hai, *partition evolution*: khi tenant lớn cần `bucket(tenant)`, Iceberg đổi spec
  mà không rewrite (NB5: 2 spec cùng tồn tại); Delta phải rewrite bảng hoặc dùng liquid clustering,
  tính năng mà hỗ trợ giữa Flink/Trino còn tuỳ phiên bản.
- Loại **Apache Hudi**. Merge-on-read và record index tối ưu cho upsert/CDC; workload này append-only
  hơn 99.9%, nên trả chi phí timeline/index mà không được lợi gì.
- Loại **Parquet + Hive partitions**. Không có atomic commit cho micro-batch 60 s (reader thấy file
  đang ghi dở); không có snapshot để rollback ở FM1; người dùng quên `WHERE dt=` thì quét toàn bảng
  (NB5: ~\$220/ngày với 10K query ở quy mô 512 MB/file).

**D2 — Catalog: chọn Iceberg REST catalog (Apache Polaris).**
- Loại **AWS Glue**. Chạy được, nhưng phân quyền chi tiết phải đi qua Lake Formation, tức hai policy
  plane cho cùng một bảng, và khoá chặt vào một cloud.
- Loại **Hive Metastore**. Không có credential vending: engine cầm IAM role đọc cả bucket, nên không
  thể giới hạn quyền đọc Bronze (có text) cho riêng role `incident_reviewer`. Đây là yêu cầu (3).
- Loại **JDBC/SQL catalog** (thứ lab dùng). Không có authN/authZ; một DB duy nhất là single point.
- Cái giá phải trả: phải tự vận hành Polaris (HA, backup). Chấp nhận, vì đó là ranh giới bảo mật.

**D3 — PII: tokenize trong Flink *trước* lần ghi lakehouse đầu tiên.**
- Cách làm: HMAC-SHA256 có key (key trong KMS, xoay key theo quý) cho e-mail/điện thoại/ID → token
  tất định `<EMAIL:f5466a846b16>`, cộng NER cho tên/địa chỉ trong free text. Token tất định nên vẫn đếm
  được "bao nhiêu user bị ảnh hưởng" mà không thấy PII. Bản gốc vào bảng VAULT mã hoá, TTL 7 ngày.
- Loại **redact ở Silver**. Khi đó Bronze giữ raw PII 7 ngày, ai đọc Bronze cũng là người đọc PII,
  vi phạm thẳng yêu cầu (3); mỗi yêu cầu xoá dữ liệu còn phải rewrite 7 ngày file.
- Loại **Parquet column encryption, giải mã khi đọc**. PII vẫn nằm trên đĩa; ai có key là thấy tất cả.
  Quan trọng hơn: PII nằm *bên trong* cột prompt, nên mã hoá cột nghĩa là mã hoá cả prompt, và incident
  review lại phải giải mã toàn bộ.
- Loại **redact ở SDK client**. Hàng trăm SDK/phiên bản của khách hàng, không kiểm soát được.
- Rủi ro còn lại: Kafka giữ raw 24 h. Giảm nhẹ bằng mã hoá at rest, ACL chỉ cho principal của Flink,
  retention 24 h. Cái giá: CPU cho NER (≈ 35 vCPU, xem §5).

**D4 — Layout: tách Bronze rộng (có text) và Silver hẹp (chỉ metric).**
- Loại **một bảng rộng duy nhất**. NB7 cho thấy projection pushdown làm cột text gần như không tốn gì
  với scan phân tích, nên vấn đề không nằm ở I/O. Vấn đề là: (a) phân quyền — grant cấp bảng thì engine
  nào cũng hiểu như nhau, còn column masking thì Trino/Spark/Flink xử lý không đồng nhất; (b) sort order
  khác nhau — dashboard cần `(tenant, ts)`, incident review cần `ts`; (c) chi phí compaction — Silver
  50 GB/ngày compact hàng giờ rất rẻ, còn compact 1.23 TB/ngày mỗi giờ thì không.
- Loại **mỗi request một object** (pointer layout của NB7). 1B PUT/ngày × \$0.005/1K = **\$5 000/ngày ≈
  \$150 K/tháng**. Pointer chỉ hợp lý cho blob lớn (frame 64 KB+), là thảm hoạ với object 5 KB.
- Nén: **Parquet zstd level 3**. Loại snappy (giả định 2.5× thay vì 4× trên text → Bronze +\$153/tháng);
  loại gzip (tỷ lệ tương tự zstd nhưng giải nén chậm hơn nhiều, làm chậm incident review và compaction).

**D5 — Partitioning và clustering: `day(ts)` + sort theo `(tenant_id, ts)` ở Silver/Gold.**
- Loại **identity(tenant_id)**. 10 000 tenant × 1 440 commit/ngày → tới **14.4M file/ngày** trong
  trường hợp xấu; tenant đuôi dài sinh file vài KB (NB6: chi phí request và planning tăng phi tuyến).
- Loại **hour(ts)**. Gấp 24 lần số partition và manifest entry, mà không pruning thêm được gì so với
  min/max `ts` có sẵn trong file của partition ngày; retention chỉ cần độ mịn ngày.
- Loại **bucket(tenant, N) ngay từ đầu**. Tenant lớn nhất chiếm 30% traffic làm một bucket phình to (skew);
  sort trong compaction xử lý skew tốt hơn. Nếu cần sau này, thêm bằng partition evolution (NB5), không rewrite.
- Bằng chứng: NB2 sau Z-order prune 54/55 file; NB6 clustering skip 90%. Mục tiêu MVP A4 là ≥ 90%.

**D6 — Lifecycle: S3 Standard + drop theo partition + expire + orphan sweep, tất cả qua table format.**
- Loại **S3 Standard-IA / Intelligent-Tiering cho Bronze**. IA tính phí tối thiểu 30 ngày: 1.23 TB/ngày
  × 30 ngày × \$0.0125 = **\$463/tháng**, trong khi Standard 9 ngày × \$0.023 = **\$255/tháng** — IA đắt
  hơn 1.8× cho dữ liệu sống 7 ngày. Intelligent-Tiering không tier object < 128 KB và thu phí monitoring theo object.
- Loại **S3 lifecycle rule xoá theo prefix**. Nó xoá file sau lưng catalog → metadata trỏ tới file không tồn
  tại → query lỗi. Retention phải là một commit của bảng.
- Loại **chỉ `DELETE` rồi để đó**. NB6 + PoC: delete và expiry đều *không* xoá byte; time travel vẫn trả
  18 000 dòng cũ sau delete. Phải chạy đủ chuỗi delete → expire → sweep.
- Gold (315 GB/năm, \$7/tháng) để luôn ở Standard; chuyển Glacier chỉ tiết kiệm ~\$6/tháng mà làm chậm query năm.

**D7 — Ingestion và serving: Flink commit 60 s; dashboard đọc Gold qua Trino.**
- Loại **Spark Structured Streaming trigger 5 phút**. Freshness = trigger + aggregate + commit > 5 phút, trượt SLA.
- Loại **commit mỗi 5 giây**. 17 280 commit/ngày/bảng; small files và metadata phình (NB6: 200 commit đã cần checkpoint).
- Loại **ClickHouse/Druid làm lớp serving**. Đạt sub-second dễ dàng, nhưng tạo bản sao thứ hai với một
  policy retention/PII thứ hai cần giữ đồng bộ — đúng lifecycle bug của NB7 (index ngoài còn trả 8 doc đã xoá).
  Sẽ xem lại nếu SLA dashboard xuống < 1 s.

## 4. Failure modes (chuyện gì hỏng lúc 3 giờ sáng)

**FM1 — Deploy redactor bị lỗi regex, PII lọt vào Bronze** *(time travel + snapshot expiry, NB3/NB6)*.
- Phát hiện: một prober gửi request chứa **canary PII giả** mỗi phút (như `CANARIES` trong PoC); một job
  quét các file *mới được thêm* bởi từng snapshot (manifest entries), giải nén rồi so regex + chuỗi canary.
  Thấy 1 hit là page on-call. Có thêm sample 0.1% bằng detector mạnh hơn.
- Rollback: (1) dừng Flink; (2) tìm snapshot xấu đầu tiên qua snapshot summary property `flink.job-version`;
  (3) `rollback_to_snapshot(last_good)` cho Bronze; (4) **lập tức** expire các snapshot xấu rồi orphan sweep
  — NB6 đã đo rằng expire một mình không xoá file, nên bỏ bước sweep thì PII vẫn nằm trên S3; (5) replay
  Kafka từ offset lưu trong snapshot `last_good` bằng redactor đã sửa. Kafka giữ 24 h nên **phải phát hiện
  trong 24 h**; canary 1 phút cho detection < 5 phút.

**FM2 — Small-file storm khi autoscale** *(compaction/clustering, NB2/NB6)*.
- Kịch bản: traffic tăng vọt, autoscaler đẩy parallelism của sink 24 → 192; file trung bình còn ~4 MB,
  planning của Trino tăng, p95 dashboard vượt SLA.
- Phát hiện: job 5 phút đọc metadata table `files` và cảnh báo khi kích thước file trung bình của partition
  hôm nay < 64 MB hoặc > 20 000 file/partition.
- Xử lý: compaction ưu tiên cho partition hôm nay + `rewrite_manifests`. Sửa gốc: `write.distribution-mode
  = hash` và tách parallelism của sink khỏi source. Không cần rollback dữ liệu — compaction là commit mới, đọc vẫn đúng.

**FM3 — Schema drift từ team API** *(schema evolution + field ID, NB1/NB5)*.
- Kịch bản: team API đổi `latency_ms` → `latency_millis`, hoặc `tokens` int → string.
- Phát hiện: schema registry kiểm tra BACKWARD compatibility trong CI; tỷ lệ dead-letter của Flink > 0.1% thì báo động.
- Xử lý: rename được áp dụng như một rename của Iceberg (giữ field id 4, metadata-only — NB5), nên query Gold
  không vỡ. Đổi kiểu không tương thích bị chặn (như NB1 chặn `age='thirty'`) và đi vào DLQ; replay sau khi
  có mapping. Nếu một schema sai đã được commit thì revert bằng `update_schema` + rollback snapshot.

**FM4 — Dữ liệu đến muộn và ranh giới ngày UTC** *(bug thật ở NB4)*.
- Kịch bản: client reconnect gửi event trễ 3 h; bucket 5 phút đã đóng nên Gold thiếu số. Hoặc một engine
  cast ngày theo múi giờ local, như NB4 (8 ngày lệch 7 giờ).
- Phát hiện: job đối soát lúc 03:00 so số dòng Gold với Silver theo ngày (lệch > 0.1% là cảnh báo); theo dõi
  histogram `ingest_ts − ts`; kiểm tra phân bố số dòng theo giờ UTC (ngày đầu/cuối bị hụt là dấu hiệu lệch múi giờ).
- Xử lý: Gold trong ngày mang `is_final = false`; lúc D+1 03:00 tính lại Gold của ngày D từ Silver (còn được
  vì Silver giữ 7 ngày) bằng overwrite partition, rồi đặt `is_final = true`. Mọi session engine được cấu hình
  `TimeZone = UTC`.

**FM5 — Job retention chạy sai cửa sổ hoặc chết lặng lẽ.**
- Phát hiện: SLO hằng ngày — `min(ts_day)` của Bronze ≥ today − 7; **0 file vật lý có dòng cũ hơn cutoff**
  (đúng check của PoC); số dòng D−1 > 0 và khớp Silver ±5%.
- Rollback khi lỡ xoá nhầm ngày: tách hai pha — DELETE lúc 01:00, expire + sweep lúc 13:00 — tạo **cửa sổ
  undo 12 giờ** bằng `rollback_to_snapshot`. Đánh đổi: thời hạn xoá vật lý thành 7 ngày + 13 giờ; ghi rõ trong
  policy là "≤ 8 ngày".

## 5. Chi phí ước lượng

Đơn giá giả định: S3 Standard \$0.023/GB-tháng, IA \$0.0125 (tối thiểu 30 ngày), PUT \$0.005/1K, GET
\$0.0004/1K, MSK storage \$0.10/GB-tháng, vCPU EC2 Graviton ≈ \$0.041/giờ.

| Hạng mục (storage + request) | Phép tính | \$/tháng |
|---|---|---:|
| Bronze redacted | 1B × 4.7 KB text ÷ 4 (zstd) × 1.05 (retry trùng) = **1.23 TB/ngày**; giữ 9 ngày (7 + 1 chờ retention + 1 tombstone compaction) = 11.1 TB × \$0.023 | 255 |
| Silver metrics | 1B × 300 B ÷ 6 = 50 GB/ngày × 9 ngày × \$0.023 | 10 |
| Gold 5 phút, 1 năm | 10K tenant × 2 model × 288 bucket × 50% lấp đầy = 2.88M dòng/ngày × 300 B = 0.86 GB/ngày × 365 = 315 GB × \$0.023 | 7 |
| Vault + metadata Iceberg | 63 GB vault + ~1% của Bronze (111 GB) | 4 |
| Kafka 24 h | 5 TB ÷ 3 (nén) × RF 3 ≈ 5 TB, cấp 6 TB × \$0.10 | 600 |
| PUT | (1.23 TB ÷ 8 MB part × 2 lần ghi do compaction + manifest) ≈ 337K/ngày × 30 = 10.1M × \$0.005/1K | 51 |
| GET (dashboard, chưa tính cache) | 1 000 dashboard × 10 panel mỗi 5 phút = 2.88M query/ngày × 10 GET × 30 = 864M × \$0.0004/1K | 346 |
| **Tổng storage + request** | | **≈ 1 273** |

**Kết luận:** ≈ \$1.27 K/tháng, tức **25% budget \$5 K**. Độ nhạy: nếu text chỉ nén được 2× (thay vì 4×),
Bronze tăng lên \$511 và tổng thành \$1.53 K — vẫn đạt. Phản chứng: giữ raw 1 năm = 1.825 PB ≈ **\$38 K/tháng**,
nên lifecycle (D6) là biện pháp quyết định chứ không phải tối ưu phụ. Đòn bẩy lớn nhất còn lại là Kafka
(47% tổng): giảm retention xuống 12 h tiết kiệm \$300 nhưng thu hẹp cửa sổ phát hiện của FM1 — tôi giữ 24 h.

**Compute** (ngoài cap storage, liệt kê cho đủ): Flink tokenizer/NER — peak 35K req/s ÷ 1 500 req/s/vCPU
× 1.5 headroom ≈ 36 vCPU × 730 h × \$0.041 ≈ **\$1 080**; compaction 1.23 TB/ngày ở 30 MB/s/core ≈ 11.4
core-giờ/ngày ≈ **\$14**; Trino 4 × r7g.2xlarge ≈ **\$1 255**; 6 broker MSK ≈ **\$1 750**. Tổng compute
≈ \$4.1 K/tháng; toàn hệ thống ≈ \$5.4 K/tháng.

## 6. MVP một tuần

**Slice:** một pipeline đầu-cuối ở **1/100 quy mô** (10M req/ngày ≈ 116 req/s, burst 350 req/s), chạy trên
máy dev: Redpanda → Flink (tokenizer + Iceberg sink 60 s + Gold 5 phút) → MinIO + Polaris → Trino, cùng các
job maintenance. Chưa làm: NER (chỉ regex), multi-region, HA cho Polaris.

| Ngày | Việc |
|---|---|
| 1–2 | Tokenizer + Iceberg sink cho Bronze/Silver; Polaris với 2 role (`analyst`, `incident_reviewer`) |
| 3 | Gold 5 phút + query dashboard theo tenant trên Trino; probe đo freshness |
| 4 | Retention: delete → expire → sweep (đã spike trong PoC); compaction + sort theo tenant |
| 5 | Load test + chaos: `kill -9` Flink giữa commit, canary PII, deploy redactor lỗi (diễn tập FM1) |

**Tiêu chí nghiệm thu:**
- **A1.** 0 giá trị PII trong *mọi* file Parquet (đọc giải nén từng cột string), và negative control (file chưa redact) cho > 0 hit.
- **A2.** Sau một chu kỳ retention: 0 file vật lý chứa dòng cũ hơn cutoff, và Gold vẫn đủ mọi ngày.
- **A3.** Freshness từ event → Gold: p95 ≤ 5 phút, đo bằng probe có timestamp.
- **A4.** Query lọc theo tenant trên Silver prune ≥ 90% file (đếm bằng `plan_files()`).
- **A5.** Tỷ lệ nén đo trên prompt mẫu đưa vào bảng §5, cho ra storage dự phóng ≤ \$5 K ở 1B/ngày.
- **A6.** Sau `kill -9`: không có `request_id` trùng trong Silver; orphan sweep tìm được file chưa commit.
- **A7.** Role `analyst` đọc Bronze bị catalog từ chối.

**Cơ chế khó nhất đã được kiểm chứng bằng PoC** ([`poc/`](poc/)) trên stack lightweight của lab. Trong PoC,
tokenizer chạy trước lần ghi đầu tiên; quét 19 file Parquet được **0 hit**, còn negative control cho 4 hit.
Retention xoá 7 ngày → giữ lại 14 000 dòng; `DELETE` bỏ 2 file mỗi bảng và **rewrite 0 file** (cutoff là
00:00 UTC trùng ranh giới `day(ts)`). Sau DELETE, time travel vẫn đọc được 18 000 dòng; sau khi expire 9 snapshot
và sweep 13 file mỗi bảng, còn **0 file vật lý có dòng cũ**, trong khi Gold 5 phút vẫn phủ đủ 9 ngày. A1 và A2
là hai mệnh đề mà nếu sai thì kiến trúc này sai; MVP chỉ cần lặp lại chúng ở quy mô lớn hơn và trên S3.

## Nguồn tham khảo

- Apache Iceberg — Table spec (hidden partitioning, partition evolution, snapshot) và Maintenance
  (expire snapshots, remove orphan files, rewrite manifests): https://iceberg.apache.org/docs/latest/
- PyIceberg API (delete, `maintenance.expire_snapshots`, `inspect`): https://py.iceberg.apache.org/
- Apache Polaris — REST catalog, credential vending: https://polaris.apache.org/
- Amazon S3 pricing (storage class, minimum storage duration, request): https://aws.amazon.com/s3/pricing/
- Kết quả đo trong lab này: NB2 (pruning 55×), NB4 (lệch múi giờ), NB5 (field id, partition evolution),
  NB6 (expire không xoá file, orphan), NB7 (pointer vs inline, lifecycle bug của index ngoài).
- Phạm vi pháp lý: bài **không** khẳng định tuân thủ một luật cụ thể nào (GDPR, Nghị định 13/2023/NĐ-CP…);
  "redact trước khi đọc" và "xoá vật lý ≤ 8 ngày" là yêu cầu kỹ thuật của đề, cần pháp chế xác nhận khi áp dụng thật.
