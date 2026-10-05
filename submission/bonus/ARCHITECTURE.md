# Bonus — LLM Observability ở quy mô 1B requests/ngày

**Tác giả:** Vũ Minh Điềm · 2A202602858 · **Topic A** · PoC: [`poc/pii_retention_poc.py`](poc/pii_retention_poc.py) ([output](poc/OUTPUT.txt))

> Giá cloud dùng bảng giá AWS us-east-1 on-demand công khai, làm tròn (xem mục Nguồn).
> Các tỉ lệ nén và throughput là **giả định**, được đánh dấu *(GĐ)* và có kế hoạch đo trong MVP.

---

## 1. Problem statement

Một foundation-model API log mọi request/response: **1B request/ngày × ~5 KB = 5 TB/ngày raw**.
Trung bình 11.6K req/s; giả định peak 3× ≈ **35K req/s (~520 MB/s raw)**. Yêu cầu:

1. Dashboard cost và latency theo tenant, **refresh mỗi 5 phút**.
2. Prompt/response đầy đủ giữ **7 ngày** cho incident review. Sau đó chỉ còn **aggregates trong 1 năm**.
3. **PII được redact trước khi bất kỳ ai đọc.**
4. Tổng chi phí storage **≤ $5K/tháng**.

**Vì sao khó.** Mỗi yêu cầu kéo về một hướng khác nhau:

- Yêu cầu (3) buộc redact *trong luồng*, ở 35K req/s, nên không thể dùng ML đắt tiền cho từng request.
- Yêu cầu (2) đòi bytes phải *thực sự biến mất*. Nhưng time travel và snapshot (NB3, NB6, NB8) được thiết kế để giữ file cũ.
- Yêu cầu (1) cần dữ liệu tươi, nhưng commit thường xuyên lại sinh ra small files (NB2, NB6).
- Yêu cầu (4) khiến việc giữ raw không nén 7 ngày là không thể. Bảng dưới đây tính chi phí của cách đó.

| Cách lưu raw 7 ngày | Dung lượng | Chi phí/tháng |
|---|---|---|
| JSON không nén, nhân 2 bản raw + redacted | 70 TB | $1,610 |
| Như trên, giữ 30 ngày | 300 TB | $6,900, vượt cap |

## 2. Kiến trúc

```
  API gateways (1B req/day, peak 35K req/s)
        │  JSON events (request_id, tenant_id, model, tokens, latency, cost, prompt, response)
        ▼
  Kafka  (retention 24 h, RF=3)  ── raw PII chỉ tồn tại ở đây, mã hoá at-rest, không ai được consume trừ redactor
        │
        ▼
  ┌──────────────── Stream job: REDACTOR (regex + checksum validators, redactor_version) ─────────────┐
  │  PII → <KIND:token>  token = HMAC(tenant_data_key, value), bảng chữ cái a–z  [① PII tại Bronze]   │
  │  span gốc ──AES-GCM (tenant data key, wrap bởi 1 KMS CMK)──► restricted.pii_vault (7 ngày)        │
  │  dedup request_id (state 10 phút) ; sample 0.1% ─► ML-NER audit (offline) ; canary injector 1/phút│
  └───────────────┬─────────────────────────────────────────┬─────────────────────────────────────────┘
                  │ commit mỗi 60 s                         │ 1-min tumbling windows, watermark 2 phút
                  ▼                                         ▼
  BRONZE  iceberg: obs.bronze_requests          GOLD  iceberg: obs.gold_tenant_1m / _1h / _1d
   full redacted payload, zstd-3                  p50/p95 latency, tokens, cost, error_rate
   partition day(ingest_ts)  [② hidden part.]     theo tenant × model; giữ 365 ngày
   sort (tenant_id, ts) khi compaction [③ clustering]   ▲ hourly correction MERGE (late data)
                  │                                     │
                  ▼  hourly                             │
  SILVER  obs.silver_facts (không có text, 7 ngày) ────┘
                  │
  ┌───── Maintenance (daily 01:00 UTC) [④ lifecycle / NB6] ─────────────────────────────────────┐
  │ delete partitions ingest_day < today-7 → expire snapshots > 24 h → orphan sweep (age ≥ 24 h)│
  │ → checkpoint/rewrite manifests → "oldest file on disk" audit                                │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
  Catalog: Apache Polaris (REST)  [⑤ catalog = control plane]
   - role incident_responder: đọc obs.bronze_*  (mọi lượt đọc được audit log)
   - role analyst / dashboards: chỉ obs.gold_*   - restricted.pii_vault: break-glass, 2 người duyệt
   - credential vending: STS creds theo từng bảng, không ai có quyền s3:GetObject trực tiếp
  Query: Trino (incident review trên Bronze) · DuckDB/Trino trên Gold (dashboard 5 phút)
```

Các concept Day18 được áp dụng trong sơ đồ:

- **① Medallion + PII tại Bronze:** Bronze không bao giờ chứa raw PII.
- **② Hidden partitioning** (NB5): người dùng không thể quên partition predicate.
- **③ Clustering và file skipping** (NB2, NB6) cho hot path "filter theo tenant".
- **④ Snapshot expiry + orphan sweep** (NB6) để retention thật sự xoá bytes.
- **⑤ Catalog là control plane** (NB5, NB8): phân quyền và audit nằm ở catalog, không nằm ở đường dẫn S3.

## 3. Quyết định chính và alternatives bị loại

### D1. Redact ở đâu? → **Trong stream, trước lần ghi bền vững đầu tiên vào lake**

- **Loại "Bronze giữ raw, redact ở Silver".** Mọi người có quyền đọc Bronze đều đọc được PII. Tệ hơn, time travel giữ bản raw: NB8 đo được việc xoá subject ở v1 vẫn để lại dữ liệu ở v0. Muốn sửa thì phải rewrite, expire, rồi sweep toàn bộ 7 TB.
- **Loại dynamic masking ở query layer** (view hoặc column mask). Dữ liệu raw vẫn nằm trên S3. Bất kỳ engine nào đọc file trực tiếp (Spark với IAM role rộng, DuckDB với key bị lộ) đều bỏ qua được view. Chỉ cần một credential rò rỉ là lộ toàn bộ dữ liệu.
- **Giá phải trả:** muốn xem giá trị gốc cho incident thì phải đi qua vault break-glass. Ngoài ra, một lỗi của redactor sẽ ghi PII thẳng vào Bronze (xem F1).

### D2. Cách phát hiện PII → **Regex + validator (checksum CCCD/thẻ) inline; ML-NER chỉ chạy trên mẫu 0.1%**

- **Loại NER transformer inline.** Ở 35K req/s × 5 KB, cần cỡ 20–40 GPU *(GĐ: ~1K req/s/GPU)*, tức khoảng $15–30K/tháng, gấp 4–8 lần toàn bộ ngân sách.
- **Loại redact bằng LLM.** Kể cả với giá $0.00001/request, chi phí là 1B × $0.00001 = **$10K/ngày**.
- **Giá phải trả:** regex bỏ sót các định dạng mới. Bù lại bằng audit NER trên mẫu và canary (F1).
- **Phát hiện từ PoC:** token dạng hex 12 ký tự đôi khi toàn chữ số, nên trông như CCCD. Lần chạy đầu, chính leak-scanner của PoC báo 44 "CCCD" giả. Vì vậy token chỉ dùng bảng chữ cái a–z, tách bạch hoàn toàn với các mẫu PII.

### D3. Table format → **Apache Iceberg v2**

- **Loại Hive-style Parquet.** Không có commit nguyên tử: reader có thể thấy micro-batch ghi dở. Người dùng có thể quên `WHERE dt=`. NB5 tính ra ~$220/ngày lãng phí ở 10K query/ngày; dashboard ở đây refresh 5 phút × hàng nghìn tenant nên còn tệ hơn.
- **Loại Delta Lake.** Delta mạnh về CDF và deletion vectors. Nhưng Gold ở đây tính trực tiếp từ stream nên không cần CDF. Điều cần là partition evolution không phải rewrite: nếu traffic tăng 3× thì chuyển `day → hour` như NB5 (spec 1 và 2 cùng tồn tại). Iceberg cũng làm việc với REST catalog đa engine (Trino, Spark, DuckDB) mà không cần lớp UniForm.
- **Giá phải trả:** PyIceberg chưa có `remove_orphan_files` hay rewrite. Maintenance chạy bằng Spark procedures hoặc tự viết phép hiệu tập file (NB6, PoC).

### D4. Partitioning và layout → **`day(ingest_ts)` + sort `(tenant_id, ts)` khi compaction, file 256–512 MB**

- **Loại partition theo `tenant_id`.** Có khoảng 20K tenant *(GĐ)* và phân bố lệch: 20K × 7 ngày = 140K partition, đa số chỉ vài MB. Đây đúng là small-file problem của NB2/NB6, và metadata sẽ lớn hơn data (NB5 đo 291% ở quy mô nhỏ).
- **Loại partition theo `day(event_ts)`.** Event đến trễ hơn 7 ngày sẽ rơi vào partition đã bị xoá và "hồi sinh" nó. Partition theo `ingest_ts` cho retention chính xác. Query theo `ts` vẫn được prune nhờ min/max stats, vì `ts ≈ ingest_ts`.
- **Loại `hour()` ngay từ đầu.** Mỗi ngày có 24× số partition, mà mỗi partition chỉ khoảng 42 GB. Để dành chuyển sang `hour` qua partition evolution khi cần.
- **Hiệu quả:** 1 TB/ngày ÷ 512 MB ≈ 2,000 file/ngày. Sau khi sort theo tenant, query một tenant trong một ngày chỉ chạm vài file. NB6 đo skip 90% trên min/max stats.

### D5. Gold freshness → **Aggregation 1 phút trong stream + MERGE sửa sai mỗi giờ**

- **Loại recompute từ Silver mỗi 5 phút.** Cách này thêm 288 commit/ngày cho mỗi bảng Gold, cộng một hop trễ (stream → Silver commit → job). Độ trễ p95 khó giữ dưới 5 phút.
- **Loại OLAP store riêng (ClickHouse/Druid).** Dashboard sẽ dưới 1 giây, nhưng tạo ra system-of-record thứ hai với phân quyền và retention riêng. Đây đúng là anti-pattern "hai nguồn sự thật" của NB7. Gold chỉ khoảng 0.3 TB/năm nên Trino/DuckDB đọc đủ nhanh.
- **Giá phải trả:** event đến sau watermark 2 phút sẽ thiếu trong bucket. Job hourly MERGE `WHEN MATCHED` tính lại 2 giờ gần nhất từ Silver.

### D6. Retention → **Delete partition → expire snapshots → orphan sweep (age guard 24 h) → audit file cũ nhất**

- **Loại S3 Lifecycle Expiration theo prefix.** S3 xoá file mà metadata vẫn tham chiếu, nên query time travel hoặc plan sẽ gặp `FileNotFound`. Lifecycle không hiểu ngữ nghĩa bảng.
- **Loại chuyển sang Glacier.** Giá chỉ $0.004/GB, nhưng vi phạm yêu cầu "sau 7 ngày chỉ còn aggregates", và dữ liệu đã redact vẫn là dữ liệu người dùng.
- **Loại "chỉ expire snapshots".** NB6 và PoC đo được expiry **không xoá byte nào** (PoC: 813 KB → 817 KB). Phải có thêm bước sweep (817 → 554 KB).
- **Cam kết:** dữ liệu tồn tại ≥ 7 ngày và bị xoá vật lý trước **ngày thứ 9**: 7 ngày giữ + 24 h giữ snapshot + 24 h age guard.

### D7. Catalog và governance → **Apache Polaris (Iceberg REST) với credential vending**

- **Loại AWS Glue + IAM theo path.** Phân quyền gắn với prefix S3 chứ không gắn với bảng. Muốn audit "ai đọc Bronze" phải lục CloudTrail data events, vốn tốn tiền ở 1B object-ops. Ngoài ra còn bị khoá vào một nhà cung cấp.
- **Loại Hive Metastore.** Không có commit nguyên tử qua REST, không có credential vending, không có RBAC theo namespace.
- **Giá phải trả:** phải tự vận hành Polaris (HA, backup). Catalog trở thành single point of failure cho mọi lượt ghi.

### D8. Nén → **zstd level 3**

- **Loại snappy.** Ghi nhanh hơn, nhưng file to hơn khoảng 30–40% với text *(GĐ)*, tức khoảng +$80/tháng và nhiều bytes scan hơn khi xử lý incident.
- **Loại zstd-19.** Chỉ nhỏ hơn khoảng 10% nhưng tốn CPU gấp 5–10 lần, chạy trên đường nóng 35K req/s.

## 4. Failure modes (kịch bản 3 giờ sáng)

### F1. Redactor bỏ sót PII

Ví dụ: một tenant bắt đầu gửi số hộ chiếu, hoặc lỗi kiểu token trùng dạng PII như PoC đã gặp.

- **Phát hiện**
  - Canary injector đẩy 1 bản ghi PII giả mỗi phút qua *đúng* đường production. Monitor quét Bronze; nếu thấy chuỗi canary raw trong ≤ 5 phút thì page on-call.
  - Audit NER trên mẫu 0.1% đo tỉ lệ rò rỉ theo `redactor_version`.
- **Rollback** (gắn với **time travel**)
  1. Dừng consumer.
  2. Xác định khoảng snapshot bị ảnh hưởng theo `redactor_version` và `ingest_ts`.
  3. Rewrite các partition đó bằng redactor v+1 (`overwrite` theo partition).
  4. Ngay lập tức expire mọi snapshot cũ hơn bản rewrite (bỏ qua mức giữ 24 h) và chạy orphan sweep.
  5. Kiểm chứng bằng cách quét **bytes trên đĩa**, giống PoC (`0 raw PII in Bronze files`), không chỉ quét kết quả query.
- **Lý do:** NB8 đã cho thấy xoá ở version hiện tại không xoá được version cũ.

### F2. Schema drift từ upstream

Ví dụ: `latency_ms` đổi từ int sang string, hoặc thêm trường `reasoning_tokens`.

- **Phát hiện:** data contract trong redactor. Thay đổi *thêm cột* được chấp nhận qua schema evolution theo field-ID (NB5: rename/add không rewrite data). Thay đổi *kiểu không tương thích* bị chuyển vào `obs.dlq`. Báo động khi DLQ > 0.1% trong 5 phút.
- **Rollback:**
  - Nếu Gold đã nhận dữ liệu sai: `manage_snapshots().rollback_to_snapshot(id)` về snapshot trước commit lỗi, rồi replay từ Kafka.
  - Kafka chỉ giữ 24 h, nên quá 24 h phải tính lại Gold từ Silver.
  - Runbook ghi rõ: **sửa trong 24 h, nếu không thì mất khả năng replay raw**. Đây là chủ ý, vì raw có PII.

### F3. Compaction ngừng chạy 3 đêm liền

- **Hệ quả:** commit 60 s × 16 writer = 23K file/ngày, tức gần 70K file nhỏ. Thời gian plan query incident tăng mạnh, metadata phình (NB5), và chi phí GET tăng (NB6: 200 → 11 file giảm request 50×).
- **Phát hiện:** cảnh báo khi kích thước file trung bình < 64 MB ở partition cũ hơn 2 giờ, hoặc > 5K file mỗi partition.
- **Rollback:** compaction là thao tác idempotent và reader có snapshot isolation, nên chỉ cần chạy lại. Nếu compaction ghi ra layout sai (sort sai cột) thì `rollback_to_snapshot` và chạy lại, không mất dữ liệu.

### F4. Retention chỉ chạy một nửa

Expire chạy được nhưng sweep lỗi: bill không giảm, và prompt cũ hơn 9 ngày vẫn nằm trên đĩa. Hoặc ngược lại, sweep xoá nhầm file của một writer chưa commit.

- **Phát hiện:**
  - Job audit hằng ngày đọc file cũ nhất còn trên đĩa, như PoC (`oldest ts left on disk ≥ cutoff`). Báo động nếu `ingest_day < today-9`.
  - Theo dõi tổng bytes Bronze so với dải kỳ vọng 8–10 TB.
  - Nếu sweep xoá nhầm: reader gặp `FileNotFound`.
- **Phòng ngừa:** age guard 24 h, lớn hơn thời gian writer dài nhất (NB6).
- **Rollback:** S3 versioning giữ noncurrent version **1 ngày**, đủ để khôi phục file xoá nhầm. Đánh đổi là dữ liệu tồn tại thêm 1 ngày, đã tính vào mốc "ngày thứ 9" ở D6.

### F5. Retry của client gây trùng `request_id`

- **Hệ quả:** Gold đếm cost hai lần. NB4 đo được 5% bản trùng trong dữ liệu mẫu.
- **Xử lý:** dedup trong stream theo `request_id`, giữ state 10 phút. Trùng ngoài cửa sổ đó được bắt bởi job MERGE hằng giờ dedup trên Silver.
- **Đo lường:** chênh lệch giữa `count(distinct request_id)` và `requests` trong Gold, theo ngày.

## 5. Chi phí (back-of-envelope)

### Storage (thuộc cap $5K)

| Thành phần | Phép tính | TB | $/tháng |
|---|---|---:|---:|
| Bronze redacted | 5 TB/ngày ÷ 5× zstd *(GĐ)* = 1 TB/ngày; × (7 giữ + 1 snapshot + ~2 bản chờ compaction/sweep) | 10 | 10,000 GB × $0.023 = **$230** |
| Silver facts (không text) | 1B × 40 B *(GĐ)* = 40 GB/ngày × 8 | 0.32 | **$7** |
| Gold 1 năm | Bucket 1 phút chỉ giữ 7 ngày, sau đó rollup 5 phút: 30K cặp tenant×model active *(GĐ)* × 288 bucket = 8.6M dòng/ngày × 80 B = 0.7 GB/ngày × 365, cộng 10% cho rollup giờ/ngày | 0.28 | **$6** |
| PII vault | 20% request có PII × 3 span × 40 B = 24 GB/ngày × 8 | 0.19 | **$4** |
| Kafka (MSK) | 5 TB/ngày ÷ 2.5× lz4 = 2 TB × 24 h × RF 3 = 6 TB × $0.10/GB-tháng | 6 | **$600** |
| S3 requests | PUT: 23K file/ngày + compaction ≈ 30K × $0.005/1K ≈ $5/tháng. GET dashboard: 500 dashboard × 288 refresh × 20 file = 2.9M/ngày × $0.0004/1K = $35/tháng. Incident + maintenance ≈ $10 | — | **$50** |
| KMS | **1 CMK** wrap 20K tenant data key (data key lưu trong vault); 20K CMK riêng sẽ tốn **$20K/tháng** | — | **$1 + ~$10 request** |
| **Tổng storage** | | **~17 TB** | **≈ $910 / tháng (18% cap)** |

**Độ nhạy của ước tính:**

| Kịch bản | Tác động | Tổng storage/tháng |
|---|---|---|
| Nén chỉ 3× thay vì 5× | Bronze 16.7 TB → $384 | ≈ $1,060 |
| Traffic tăng 3× (3B req/ngày) | Bronze $690 + Kafka $1,800 + … | ≈ $2.6K, vẫn dưới cap |

Yếu tố thực sự đe doạ cap là **tăng retention**, không phải traffic: giữ prompt 30 ngày ở 5× nén tốn 30 TB × $23 = $690 cho Bronze. Cap $5K vỡ khi giữ khoảng 185 ngày ((5,000 − 680) ÷ $23/TB ≈ 188 TB), hoặc sớm hơn nhiều nếu lưu thêm một bản raw chưa redact.

### Compute (ngoài cap, nêu để thiết kế khả thi)

| Thành phần | Phép tính | $/tháng |
|---|---|---:|
| MSK brokers | 3 × kafka.m5.2xlarge × $0.84/h × 730 | $1,840 |
| Redactor stream | Regex 4 pattern ≈ 200 µs/req → ~5K req/s/vCPU *(GĐ)*. Peak 35K → 7 vCPU, ×2 cho parse/encode/write → 16 vCPU. Autoscale 1–3 × c6i.2xlarge, trung bình 1.5 × $0.34 × 730 | $372 |
| Gold aggregation | 1 × c6i.xlarge × $0.17 × 730 | $124 |
| Compaction + sort | 1 TB/ngày ÷ 100 MB/s/node *(GĐ)* ≈ 2.8 node-giờ/ngày × $0.34 × 30 | $29 |
| Query (Trino) | 2 × r6i.2xlarge × $0.504 × 730, incident review scale-to-zero | $736 |
| Maintenance + audit NER 0.1% | 1M req/ngày trên 1 GPU spot vài giờ | ~$60 |
| **Tổng compute** | | **≈ $3,160** |

**Tổng toàn hệ thống ≈ $4.1K/tháng.**

## 6. MVP một tuần

**Slice:** 1% traffic thật được replay (10M request/ngày, khoảng 116 req/s) chạy qua Kafka → redactor → Iceberg Bronze trên MinIO/S3 qua Polaris, cộng Gold 1 phút và job retention với **đồng hồ giả lập** (1 "ngày" = 1 giờ).

| Ngày | Việc | Tiêu chí nghiệm thu |
|---|---|---|
| 1–2 | Redactor + Bronze + vault + canary | Quét bytes trên đĩa: **0 match** regex PII và **0/N canary raw** trên 10M bản ghi (PoC đã chạy trên 30K bản ghi: 0 match, 0/4 canary) |
| 2 | Đo throughput redactor | ≥ 4K req/s/vCPU. Nếu thấp hơn thì cập nhật bảng compute *trước khi* cam kết ngân sách |
| 3 | Gold 1 phút + dashboard | Freshness (commit Gold − `ts` của event) p95 < 3 phút |
| 4 | Compaction + sort tenant | Query 1 tenant × 1 ngày bỏ qua ≥ 90% file, chứng minh bằng `plan_files()` và min/max (như NB6) |
| 5 | Retention + audit | Sau "ngày 9", không còn file nào có `ingest_day < cutoff` trên đĩa; bytes giảm sau sweep, không chỉ sau expire; Gold giữ nguyên số dòng (PoC: 26,902 → 26,902) |

**Cơ chế khó nhất** là "PII không bao giờ chạm đĩa" và "retention xoá bytes thật". PoC đã kiểm chứng cả hai cục bộ, chạy được từ clean checkout:

```
Raw PII matches in Bronze files: {'APIKEY': 0, 'EMAIL': 0, 'CCCD': 0, 'PHONE': 0}   canaries found raw: 0/4
Table bytes: 797 KB → delete 813 KB → expire 817 KB → sweep 554 KB   (swept 2 files)
  [PASS] expiry alone does not free bytes      [PASS] no expired-day data on disk
```

Lệnh chạy: `.venv\Scripts\python.exe submission/bonus/poc/pii_retention_poc.py` (cần chạy `pip install -r requirements.txt` trước).
**Giới hạn của PoC:** dùng SQLite catalog thay cho Polaris; không có Kafka; ts đóng vai `ingest_ts`; vault chưa mã hoá; regex chưa đủ mọi loại PII.

## Nguồn

- Apache Iceberg spec (partition transforms, snapshot expiry, `remove_orphan_files`): https://iceberg.apache.org/spec/ và https://iceberg.apache.org/docs/latest/maintenance/
- PyIceberg API (`delete`, `expire_snapshots`, `update_spec`): https://py.iceberg.apache.org/api/
- Apache Polaris (REST catalog, credential vending): https://polaris.apache.org/
- Bảng giá AWS us-east-1: S3 https://aws.amazon.com/s3/pricing/ · MSK https://aws.amazon.com/msk/pricing/ · EC2 https://aws.amazon.com/ec2/pricing/on-demand/ · KMS https://aws.amazon.com/kms/pricing/ (giá làm tròn, cần kiểm tra lại tại thời điểm triển khai)
- Số liệu đo trong lab này: NB2, NB4, NB5, NB6, NB7, NB8 (`submission/notebooks/`)
- Phạm vi pháp lý: yêu cầu "redact PII" ở đây là yêu cầu nội bộ của đề. Nếu dữ liệu thuộc phạm vi Nghị định 13/2023/NĐ-CP hoặc GDPR, cần rà soát riêng; thiết kế này không phải kết luận tuân thủ.
