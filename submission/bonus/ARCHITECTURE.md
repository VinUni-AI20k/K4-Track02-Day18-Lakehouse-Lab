# Bonus — LLM Observability Lakehouse ở quy mô 1B requests/ngày

**Học viên:** Nguyễn Phúc Bảo · 2A202602925 · K4-Track02-Day18
**Topic:** A — LLM observability 1B req/ngày (số liệu là đầu vào giả định của đề bài)
**PoC:** [`poc/pii_tokenize_medallion.py`](poc/pii_tokenize_medallion.py). Hướng dẫn chạy ở [`poc/README.md`](poc/README.md).

---

## 1. Problem statement

Một team foundation-model API cần log toàn bộ request/response: **1B requests/ngày × ~5 KB = 5 TB/ngày raw**
(trung bình ~58 MB/s; giả định peak gấp 3 là ~175 MB/s). Yêu cầu:

1. Dashboard **cost & latency theo tenant**, độ trễ dữ liệu **≤ 5 phút**.
2. **Prompt/response đầy đủ giữ 7 ngày** để review sự cố. Sau đó chỉ giữ **aggregates 1 năm**.
3. **PII phải được redact trước khi bất kỳ ai đọc được dữ liệu**, kể cả data engineer có quyền đọc Bronze.
4. **Chi phí storage ≤ $5K/tháng.**

Vì sao khó: chỉ riêng retention đã mâu thuẫn với ngân sách. Giữ raw 1 năm là 1,825 TB, tốn khoảng $42K/tháng
ở S3 Standard. Muốn dashboard 5 phút thì phải ghi streaming, mà streaming lại sinh small files (NB2, NB6).
"Redact trước khi đọc" nghĩa là không được có tầng nào chứa PII thô, kể cả các version cũ còn giữ để time travel.
Và tenant phân bố rất lệch (vài tenant lớn chiếm phần lớn traffic) nên không thể partition theo tenant.

---

## 2. Architecture diagram

```
                 ┌──────────────────────── INGEST (streaming, micro-batch 60 s) ───────────────────────┐
 API gateways ──►│ Kafka topic llm_calls (24 partitions, retention 3 ngày = replay buffer)             │
  (1B req/ngày)  │        │                                                                            │
                 │        ▼                                                                            │
                 │ Tokenizing writer (Flink/Spark, 16 vCPU)                                            │
                 │   [C1] schema contract: cột lạ → reject batch, gửi DLQ                              │
                 │   [C2] PII tokenize: HMAC-SHA256(key ở KMS) cho email/phone/user_id                 │
                 │        → raw PII KHÔNG bao giờ chạm object storage                                  │
                 └────────┼────────────────────────────────────────────────────────────────────────────┘
                          ▼  commit 1 lần/phút/writer (ACID snapshot)
 ┌─────────────── LAKEHOUSE (Iceberg v2 trên S3, catalog REST = Apache Polaris) ───────────────────────┐
 │ BRONZE  llm_calls_raw      partition day(ts) [C3 hidden partitioning]   zstd Parquet   TTL 3 ngày    │
 │    │  dedup theo request_id (MERGE trong cửa sổ 48h — SDK retry tạo bản trùng, NB4)                  │
 │    ▼                                                                                                 │
 │ SILVER llm_calls           partition day(ts), sort (tenant_id, ts) [C4 clustering → file skipping]   │
 │    │                       prompt/response đã tokenize                               TTL 7 ngày      │
 │    ▼  aggregate mỗi 5 phút (incremental, đọc snapshot mới từ lần trước)                              │
 │ GOLD   tenant_metrics_5m   (bucket_5m, tenant_id, model): p50/p95 latency, tokens, cost, error_rate   │
 │                            partition month(bucket_5m)     Standard 90 ngày → IA      retention 365 d │
 │                                                                                                      │
 │ MAINTENANCE (cron)  [C5]: compaction mỗi giờ (chỉ partition cũ hơn 1h) · expire_snapshots giữ 7 ngày │
 │                     → orphan sweep (chain expiry + sweep, NB6) · drop partition theo TTL qua catalog │
 │ GOVERNANCE [C6]: Polaris RBAC + credential vending; detokenize chỉ qua vault có audit log            │
 └──────────────────────────────────────────────────────────┬───────────────────────────────────────────┘
                                                            ▼
              QUERY PATH: Trino → Gold (dashboard 5 phút, p95 < 1 s) · Silver (incident review, 7 ngày)
```

Các concept Day18 được áp dụng trực tiếp vào lựa chọn thiết kế:

- **C1/C2** — schema enforcement và PII tokenization ở Bronze landing.
- **C3** — hidden partitioning `day(ts)` (NB5).
- **C4** — clustering/Z-order cho file skipping (NB2, NB6).
- **C5** — 4 job maintenance. Expiry và orphan sweep luôn chạy thành cặp (NB6).
- **Time travel / rollback** — dùng cho failure mode F1.
- **C6** — catalog là control plane (NB5).
- **Medallion** — Bronze → Silver → Gold (NB4).

---

## 3. Quyết định chính và alternatives đã loại

### D1 — Table format: chọn **Apache Iceberg v2**
- Lý do chọn: dashboard và incident review đều lọc trên `ts`. Hidden partitioning cho phép prune mà người
  viết query không cần biết cột partition. NB5 đo được pruning ratio ≥ 5× khi lọc trên `ts` chứ không phải `ts_day`.
  Partition evolution (NB5 §8) cho phép đổi `day(ts)` → `hour(ts)` khi traffic tăng mà không rewrite dữ liệu cũ.
- **Loại Delta Lake**: về ACID và time travel thì Delta tương đương (NB1, NB3). Lý do loại là đổi partition layout
  phải rewrite bảng. Ngoài ra stack có 3 engine (Flink ghi, Spark compaction, Trino đọc) cùng đi qua một REST catalog
  trung lập, mà REST catalog spec của Iceberg là chuẩn chung giữa các engine này.
- **Loại Apache Hudi**: ưu thế của Hudi là upsert nặng (Merge-on-Read). Workload này gần như append-only:
  dedup chỉ chạm cửa sổ 48h, Gold chỉ MERGE vài nghìn dòng mỗi 5 phút. Dùng Hudi thì vẫn phải trả chi phí vận hành
  compaction/cleaner/timeline mà không tận dụng được điểm mạnh đó.

### D2 — Catalog: chọn **REST catalog (Apache Polaris, self-hosted)**
- Lý do chọn: catalog là control plane. Polaris cấp credential ngắn hạn cho từng bảng (credential vending),
  phân quyền RBAC ở cấp namespace/bảng, và mọi engine dùng chung một điểm commit atomic.
- **Loại AWS Glue**: khóa vào AWS. Không có credential vending theo bảng, nên quyền phải cấp qua IAM ở mức bucket/prefix.
  Như vậy rất khó bảo đảm chỉ nhóm incident mới đọc được Silver có prompt.
- **Loại Hive Metastore**: không có commit atomic kiểu Iceberg REST (phải dùng lock bên ngoài), không có credential
  vending, không có RBAC theo bảng. Còn thêm một DB nữa phải vận hành mà không có chuẩn API cho engine mới.

### D3 — Partitioning & clustering: chọn **`day(ts)` + sort `(tenant_id, ts)` trong file**
- Phép tính: Silver ~1.25 TB/ngày (sau zstd, xem §5), file 512 MB → ~2,500 file/partition-ngày.
  Sort theo tenant làm khoảng min/max `tenant_id` của mỗi file hẹp lại. Query của một tenant nhỏ chỉ chạm vài file.
  NB6 đo được skip ≥ 50% file sau khi cluster, so với gần 0% trước khi cluster.
- **Loại `hour(ts)`**: 24 partition/ngày × 16 writer × commit mỗi phút → mỗi partition-giờ có ~960 file nhỏ trước
  compaction. Số partition nhân 24 lần cũng làm planning tốn thêm metadata. Lựa chọn này để dành cho partition
  evolution khi traffic vượt ~5× mức hiện tại.
- **Loại partition theo `tenant_id`**: giả định 10K tenant, phân bố lệch → hàng triệu file nhỏ cho long-tail,
  trong khi vài tenant lớn lại có partition khổng lồ. Small-file problem bị nhân thêm 10,000 lần.

### D4 — PII: chọn **tokenize ở ingest (trước khi chạm storage), HMAC-SHA256 deterministic**
- Lý do chọn: đáp ứng đúng nghĩa đen yêu cầu "redact trước khi bất kỳ ai đọc". Vì token là deterministic,
  vẫn `GROUP BY user` và join được. Key nằm trong KMS. Chỉ incident responder đi qua vault (có audit log) mới
  detokenize được. PoC chứng minh cơ chế này: quét byte trên đĩa không tìm thấy PII thô.
- **Loại redact ở Silver**: Bronze sẽ chứa PII thô, ai đọc được Bronze là thấy. Tệ hơn, time travel và các snapshot
  cũ (NB3, NB8) giữ lại PII cho đến khi expire **và** sweep. NB8 cho thấy xóa ở version hiện tại chưa xóa dữ liệu ở version cũ.
- **Loại masking ở view/engine**: dữ liệu ở trạng thái lưu trữ vẫn chứa PII. Engine nào không đi qua view
  (DuckDB đọc trực tiếp file, như cách lab làm) sẽ thấy dữ liệu thô. Mỗi engine mới là một lỗ hổng mới.

### D5 — Lifecycle/retention: chọn **TTL qua catalog (drop partition) + expire_snapshots → orphan sweep**
- Lý do chọn: xóa dữ liệu phải đi qua metadata. Job hằng ngày drop partition `day(ts) < today-7` ở Silver và `< today-3`
  ở Bronze, sau đó expire snapshot cũ hơn 7 ngày, rồi sweep các file không còn được tham chiếu. NB6 đo được
  expiry trên PyIceberg chỉ làm file "unreferenced" chứ không giảm byte trên đĩa nếu không có bước sweep đi kèm.
- **Loại S3 Lifecycle rule xóa theo prefix/tuổi object**: S3 xóa file mà catalog không hề biết. Snapshot hiện tại vẫn
  trỏ tới file đó, nên reader gặp `FileNotFound` lúc 3 giờ sáng. Đây là ngược lại của orphan: metadata còn mà file mất.
- **Loại giữ raw 1 năm ở Glacier Deep Archive**: 1,825 TB × $0.99/TB ≈ $1.8K/tháng, chiếm 36% ngân sách chỉ cho một bản
  backup mà đề bài không yêu cầu. Truy xuất mất 12–48h nên vô dụng cho incident review. Và giữ prompt có PII
  (dù đã tokenize) lâu hơn mục đích sử dụng là trái nguyên tắc tối thiểu hóa dữ liệu.

### D6 — Ingestion cadence: chọn **micro-batch commit 60 s/writer + compaction mỗi giờ**
- Lý do chọn: freshness của Gold = 60 s commit + tối đa 5 phút aggregate ≤ 6 phút trong trường hợp xấu nhất.
  Muốn đạt ≤ 5 phút ở p95 thì Gold job phải bám theo bucket đã đóng; nếu cần chặt hơn thì hạ commit xuống 30 s.
  Số commit: 16 writer × 1,440 = 23K commit/ngày, vẫn ở mức catalog chịu được.
- **Loại commit theo từng request**: 1B commit/ngày tương đương ~11.6K commit/giây. Xung đột optimistic concurrency
  và metadata.json phình ra sẽ làm catalog sập. Đây là phiên bản cực đoan của small-file problem.
- **Loại batch theo giờ**: rẻ hơn, file lớn ngay từ đầu, nhưng vi phạm thẳng yêu cầu dashboard 5 phút.

### D7 — Codec: chọn **Parquet + zstd level 3**
- **Loại snappy**: nén nhanh hơn nhưng text prompt/response thường lớn hơn ~30–40% so với zstd.
  Ở mức 8.75 TB Silver, khoảng chênh đó là vài TB/tháng.
- **Loại gzip/zstd level cao**: tỉ lệ nén tăng thêm vài % nhưng tốn CPU gấp nhiều lần ở writer.
  Writer là chỗ nhạy với latency (D6).

---

## 4. Failure modes (kịch bản 3 giờ sáng)

### F1 — Schema evolution đưa PII thô vào bảng *(gắn với schema enforcement + time travel)*
- **Kịch bản:** team SDK thêm field `customer_phone` vào metadata request. Writer cấu hình
  `schema_mode="merge"`/auto-evolve tự thêm cột (đúng như NB1 §4), và cột này không đi qua tokenizer.
- **Detect:** (1) schema contract ở writer: mọi cột ngoài allowlist đều bị reject vào DLQ, không bao giờ tự merge.
  (2) Catalog event "schema changed" bắn alert lên pager. (3) Job quét regex PII trên file mới mỗi 15 phút (PoC bước 4).
- **Rollback:** (1) Dừng writer. (2) `rollback_to_snapshot(last_clean)`: time travel về snapshot trước commit xấu.
  (3) **Bắt buộc** expire các snapshot chứa PII rồi sweep orphan. Nếu bỏ bước này, PII vẫn đọc được qua time travel
  (NB8: xóa ở version hiện tại không xóa version cũ). (4) Replay từ Kafka, vì Kafka giữ 3 ngày làm replay buffer.
  PoC tái hiện toàn bộ chuỗi này.

### F2 — Compaction chết âm thầm, small-file explosion
- **Kịch bản:** job compaction bị OOM từ 22h. Đến 3h sáng, partition hôm nay có ~4,800 file 5 MB thay vì ~150 file 512 MB.
  Trino mất nhiều giây chỉ để planning, p95 dashboard vượt SLO.
- **Detect:** metric từ `inspect.files()` cho mỗi partition: alert khi `avg_file_size < 64 MB` hoặc `files > 3× baseline`.
  Thêm SLO cho thời gian planning và freshness của Gold.
- **Rollback/khắc phục:** compaction là idempotent nên chạy lại cho riêng partition bị ảnh hưởng (chỉ partition cũ hơn
  1h để tránh xung đột với writer). Tạm nâng commit interval lên 5 phút. Không cần rollback dữ liệu vì đó là layout, không phải correctness.

### F3 — Retention cấu hình sai, mất dữ liệu cần cho incident review
- **Kịch bản:** ai đó đổi `expire_snapshots(older_than=1h)` hoặc thêm S3 Lifecycle rule 2 ngày cho prefix `silver/`.
  Lúc 3h sáng có sự cố cần prompt của 5 ngày trước: hoặc đã mất, hoặc reader báo `FileNotFound`.
- **Detect:** canary query mỗi giờ đọc một dòng ngẫu nhiên của ngày `today-6` ở Silver. Kèm alert khi số file bị xóa
  vượt baseline (CloudTrail `DeleteObject`) và alert cho mọi thay đổi bucket lifecycle policy.
- **Rollback:** bật S3 Versioning trên bucket, giữ noncurrent version 3 ngày, để khôi phục object bị xóa nhầm.
  Maintenance job có guard cứng `retention ≥ 7 ngày`, cấu hình thấp hơn thì job từ chối chạy
  (tương tự `enforce_retention_duration` của Delta trong NB6).

### F4 — Request trùng / đến muộn làm sai Gold
- **Kịch bản:** SDK retry khi timeout tạo bản ghi trùng `request_id` (NB4 đo được Silver < Bronze vì có bản trùng).
  Gateway ở region bị nghẽn flush log muộn 20 phút, sau khi bucket 5 phút đã đóng.
- **Detect:** metric `late_rows` cho các event có `ts < bucket đã đóng`, và `dup_ratio` theo `request_id`.
- **Khắc phục:** Silver MERGE theo `request_id` trong cửa sổ 48h. Gold MERGE lại đúng các bucket bị ảnh hưởng.
  Dashboard đánh dấu bucket "provisional" trong 30 phút đầu.

---

## 5. Ước lượng chi phí (back-of-envelope)

**Giả định đơn giá** (S3 us-east-1 list price, cần kiểm tra lại tại thời điểm triển khai): Standard $23/TB-tháng,
Standard-IA $12.5/TB-tháng, PUT $0.005/1K, GET $0.0004/1K. On-demand `m7g.xlarge` (4 vCPU) ≈ $0.163/giờ.
**Giả định nén:** JSON log text-heavy sang Parquet zstd đạt ~4×. Đây là **giả định chưa đo**. Dữ liệu synthetic
của lab nén tốt hơn thực tế nên không dùng để kiểm chứng được. Việc đầu tiên của MVP là đo tỉ lệ này trên mẫu log thật
→ **1.25 TB/ngày**. Phần "trần ngân sách" bên dưới cho thấy kể cả khi không nén thì vẫn nằm trong ngân sách.

### Storage

| Tầng | Phép tính | TB | $/tháng |
|---|---|---:|---:|
| Bronze (TTL 3 ngày) | 1.25 TB × 3 | 3.75 | 86 |
| Silver (TTL 7 ngày, có prompt) | 1.25 TB × 7 | 8.75 | 201 |
| Overhead time travel/compaction | ~20% × (3.75 + 8.75): bản cũ chờ expire 7 ngày | 2.5 | 58 |
| Gold 365 ngày | 10K tenant × 5 model × 288 bucket × (giả định 30% thưa) ≈ 4.3M dòng/ngày × ~120 B ≈ 0.5 GB/ngày → 0.19 TB/năm | 0.19 | ~3 |
| Kafka replay 3 ngày (EBS gp3 $80/TB, nén) | 3.75 TB | 3.75 | 300 |
| **Tổng storage** | | **~19** | **≈ $650** |

Requests: 16 writer × 1,440 commit × (1 data file + ~3 metadata file) ≈ 92K PUT/ngày, tức ≈ $14/tháng.
Compaction ghi lại ~2.5K file/ngày/tầng nên không đáng kể. **Tổng storage ≈ $670/tháng, khoảng 13% ngân sách $5K.**

**Mức trần ngân sách cho phép làm gì:** nếu bỏ nén (5 TB/ngày) thì Bronze + Silver = 50 TB × $23 ≈ $1,150, vẫn trong ngân sách.
Nếu giữ Silver có prompt 1 năm thay vì 7 ngày: 456 TB × $23 ≈ **$10.5K**, vượt gấp đôi. Ràng buộc thực sự đến từ
**retention**, không phải codec. Đó là lý do D5 quan trọng nhất.

### Compute (ngoài ngân sách storage, liệt kê để đầy đủ)

| Job | Phép tính | $/tháng |
|---|---|---:|
| Tokenizing writer | peak 175 MB/s ÷ ~15 MB/s/vCPU (regex + HMAC + zstd, giả định) ≈ 12 vCPU → 4 × m7g.xlarge × 730h × $0.163 | ~476 |
| Compaction mỗi giờ | rewrite 2.5 TB/ngày ÷ 50 MB/s/vCPU ≈ 14 vCPU-h/ngày × 30 × $0.04/vCPU-h (spot) | ~17 |
| Gold 5 phút + dashboard (Trino 3 node) | 3 × m7g.xlarge × 730h × $0.163 | ~357 |
| **Tổng compute** | | **≈ $850** |

---

## 6. MVP một tuần

**Slice:** một tenant synthetic, đi end-to-end: generator → tokenizing writer → Bronze → Silver (dedup) →
Gold 5 phút → một query dashboard. Chạy trên laptop với lab stack (PyIceberg + DuckDB + SQLite catalog),
thay Polaris/S3 bằng catalog local. Cơ chế giống nhau, đã được NB5 kiểm chứng.

| Ngày | Việc |
|---|---|
| 1–2 | Tokenizer + schema contract + ghi Bronze (PoC hiện tại) |
| 3 | Silver dedup theo `request_id`, Gold 5 phút p50/p95/cost theo tenant |
| 4 | Maintenance: compaction, expiry → sweep, guard retention ≥ 7 ngày |
| 5 | Diễn tập failure F1–F3 (inject lỗi, đo thời gian detect/rollback) |

**Acceptance criteria (đo được):**
1. Quét **byte thô** của mọi file Parquet trong Bronze/Silver: **0** match regex email/phone VN.
2. Batch có cột ngoài allowlist bị **reject 100%** và không tạo snapshot mới.
3. Sau khi diễn tập F1: snapshot hiện tại sạch, snapshot chứa PII đã expire, và **quét đĩa sau sweep: 0 match**.
4. Gold freshness = `now − max(bucket_end)` ≤ 5 phút. Query Gold một tenant p95 < 1 s.
5. Sau compaction: `avg_file_size` của partition cũ ≥ 64 MB (ở quy mô lab dùng ngưỡng tương đối: số file giảm ≥ 10×).

**Kết quả PoC đã chạy** (`submission/evidence/poc_bonus.txt`): 10,000 request qua 5 commit có **0** match PII trên đĩa.
Batch có cột `user_email` bị reject và không tạo snapshot. Gold ra 36 dòng (12 bucket × 3 tenant).
Commit lộ PII cố ý bị detector bắt được **1,000** match. Sau rollback, đĩa **vẫn còn 1,000** match.
Sau expire + sweep 3 file không còn được tham chiếu (1 data file, 1 manifest, 1 manifest list), còn **0** match
và dữ liệu sạch vẫn đủ 10,000 dòng. Lần chạy đầu cũng lộ ra một lỗi thiết kế thật: regex số điện thoại khớp nhầm
vào token HMAC toàn chữ số (66 false positive). Đã sửa bằng word boundary.

**Cơ chế khó nhất và cách kiểm:** khó nhất là **"không có PII ở bất kỳ đâu trên đĩa, kể cả lịch sử"**,
vì time travel chủ động giữ lại dữ liệu cũ. PoC kiểm cơ chế này bằng cách quét trực tiếp byte trên đĩa thay vì
query qua engine (engine chỉ thấy snapshot hiện tại). Cụ thể: inject một commit xấu, rollback, expire, sweep,
rồi quét lại và phải còn 0 match.

---

## Nguồn tham khảo
- Apache Iceberg spec: hidden partitioning, partition evolution, snapshot expiry — https://iceberg.apache.org/spec/
- Iceberg REST Catalog / Apache Polaris — https://polaris.apache.org/
- Delta Lake protocol (để so sánh D1) — https://github.com/delta-io/delta/blob/master/PROTOCOL.md
- Amazon S3 pricing — https://aws.amazon.com/s3/pricing/
- Bằng chứng trong lab này: NB1 (schema enforcement/evolution), NB2/NB6 (small files, clustering, maintenance),
  NB3/NB8 (time travel, xóa ở version hiện tại ≠ xóa lịch sử), NB4 (dedup retry), NB5 (hidden partitioning, catalog).
