# Bonus — LLM Observability ở quy mô 1B requests/ngày

**Người viết:** Nguyen Truong Bao · MSSV 2A202602540 · Topic **A** (BONUS-CHALLENGE.md)
**Loại:** architecture brief để bảo vệ trong design review. Không có PoC; các giả định cần đo
được liệt kê ở mục 6 và kiểm chứng trong MVP tuần đầu.

---

## 1. Problem statement

Một team foundation-model API log mọi request/response: **1B req/ngày × ~5 KB = 5 TB/ngày raw**
(trung bình 11,600 req/s ≈ 58 MB/s; giả định peak 3× ≈ 35K req/s ≈ 175 MB/s). Yêu cầu:
(1) dashboard cost & latency **theo tenant**, refresh **mỗi 5 phút**; (2) prompt/response đầy
đủ giữ **7 ngày** cho incident review, sau đó chỉ giữ **aggregates 1 năm**; (3) **PII phải được
redact trước khi bất kỳ ai đọc**; (4) chi phí storage **≤ $5K/tháng**.

Khó ở ba chỗ. Freshness 5 phút đẩy về commit thường xuyên — đúng công thức sinh small files
(NB2/NB6). "Không ai đọc PII" nghĩa là không được có một Bronze "thô" để làm sạch sau: redaction
phải xảy ra trước lần ghi bền vững đầu tiên. Và "chỉ giữ aggregates sau 7 ngày" là yêu cầu xóa
*vật lý*: NB6/NB8 cho thấy xóa khỏi version hiện tại hay expire snapshot chưa xóa byte trên đĩa.
Ngân sách storage hóa ra không phải ràng buộc chặt (mục 5); ràng buộc chặt là PII, freshness và
vòng đời dữ liệu.

## 2. Architecture

```
                    PRODUCER (API gateway, 40+ pods)
                               │  JSON log, zstd, at-least-once
                               ▼
  ┌──────────────── Kafka  (topic llm_logs, 64 partitions, retention 6 h) ─────────────────┐
  │  raw PII exists ONLY here, encrypted at rest, ACL: ingest service account only         │
  └───────────────────────────────┬─────────────────────────────────────────────────────────┘
                                  ▼
          Flink job "ingest"  ── PII tokenization (regex + NER) ──► token vault (KMS, 7-day TTL)
          exactly-once Iceberg sink, commit every 60 s           │ canary PII injected every 1 min
                                  │                              ▼
      ┌───────────────────────────┼──────────────────────────────────────────────────────────┐
      │ BRONZE  iceberg: obs.bronze_llm_calls            [C1 medallion, C3 ACID snapshots]   │
      │   tokenized prompt/response + all metadata                                            │
      │   partition: day(ts), bucket(16, tenant_id)       [C2 hidden partitioning]            │
      │   sort within file: tenant_id, ts                 [C4 clustering for tenant filter]   │
      │   retention: 7 d  → drop partition + expire + orphan sweep   [C5 maintenance pair]    │
      │   READ: incident-review role only (catalog grant) [C6 catalog = control plane]       │
      ├───────────────────────────┼──────────────────────────────────────────────────────────┤
      │ SILVER  obs.silver_llm_requests  (metadata only, NO text)                             │
      │   request_id dedup (retries), typed usage/latency/status, cost via price table        │
      │   partition: day(ts) ; sort: tenant_id ; retention 7 d                                │
      ├───────────────────────────┼──────────────────────────────────────────────────────────┤
      │ GOLD    obs.gold_tenant_5m   (tenant, model, 5-min window)  retention 1 y             │
      │   p50/p95 latency (t-digest), tokens, cost_usd, error_rate                            │
      │   incremental MERGE per window, late data ≤ 15 min  [C7 MERGE + time travel rollback] │
      │   obs.gold_tenant_1h / _1d  downsampled rollups after 30 d                            │
      └───────────────────────────┼──────────────────────────────────────────────────────────┘
                                  ▼
   REST catalog (Lakekeeper/Polaris) ── Trino (dashboards, 5-min refresh)  ── Grafana per tenant
   Nightly: compaction (rewrite_data_files) · expire_snapshots(retain 24 h) · remove_orphan_files
```

Concepts Day18 được áp dụng vào lựa chọn cụ thể (không chỉ gọi tên): **C1** medallion với ranh
giới PII nằm *trước* Bronze; **C2** hidden partitioning `day(ts)` để dashboard lọc trên `ts`;
**C3** ACID snapshot của Iceberg + exactly-once sink để retry không nhân đôi dòng; **C4**
clustering theo `tenant_id` cho hot path; **C5** cặp expire + orphan sweep để retention thật sự
xóa byte; **C6** catalog quản lý quyền đọc Bronze; **C7** MERGE và rollback theo snapshot cho Gold.

## 3. Quyết định chính và alternatives đã loại

**D1 — Table format: chọn Apache Iceberg (v2) với REST catalog.**
Loại **Delta Lake**: Delta làm được hầu hết các việc ở đây (NB1–NB4), nhưng writer chính là
Flink và reader là Trino; hệ sinh thái Flink→Iceberg sink exactly-once và hidden partition
transform (`day`, `bucket`) là điểm mạnh trực tiếp của Iceberg, còn với Delta tôi phải tự duy trì
cột `date` sinh ra — đúng cái bẫy Hive mà NB5 đo ($220/ngày cho một predicate bị quên, ở quy mô
lab). Loại **Parquet + Hive partition**: không có commit nguyên tử, nên một Flink checkpoint fail
giữa chừng để lại file nửa vời mà reader nhìn thấy; không có time travel để rollback Gold.
Loại **ClickHouse làm system-of-record**: tuyệt vời cho dashboard, nhưng giữ 7 ngày body
(~8 TB nén) trên SSD cluster đắt hơn nhiều lần S3 và khóa dữ liệu vào một engine; tôi giữ lựa
chọn thêm ClickHouse làm *cache phục vụ* Gold nếu Trino không đạt p95.

**D2 — Ingestion: Flink streaming, commit Iceberg mỗi 60 s.**
Loại **batch theo giờ**: không đạt freshness 5 phút. Loại **micro-batch 5–10 s**: 64 writer ×
8,640 commit/ngày ≈ 550K file/ngày ở Bronze, mỗi file ~2 MB — NB6 cho thấy 200 file 51 KB đã cần
compaction 18× để query hợp lý; ở quy mô này planning và GET cost tăng phi tuyến. Commit 60 s cho
64 × 1,440 = 92K file/ngày (~11 MB/file trước compaction), freshness end-to-end ≈ 60 s commit +
≤ 5 phút refresh Gold — vẫn trong SLA, và compaction đêm đưa về 256–512 MB/file.

**D3 — Partition và clustering: `day(ts)` + `bucket(16, tenant_id)`, sort `tenant_id, ts`.**
Loại **partition theo `tenant_id`**: ~20K tenant × 24 giờ ghi → hàng trăm nghìn partition nhỏ,
tenant lớn bị lệch kích thước; đây là anti-pattern over-partitioning. Loại **chỉ `hour(ts)`**:
query "cost của tenant X hôm nay" phải mở mọi file trong ngày vì min/max `tenant_id` mỗi file phủ
toàn dải — giống NB2 trước Z-order (200/200 file). `bucket(16)` giới hạn fan-out, còn sort trong
file làm min/max `tenant_id` hẹp, đúng cơ chế NB6 Job 2 đo (skip 90 %). Nếu tenant tăng gấp 10
lần, partition evolution (NB5: 2 spec cùng tồn tại) đổi sang `bucket(64)` mà không rewrite.

**D4 — PII: tokenization trong Flink trước Bronze, vault có TTL 7 ngày.**
Loại **redact ở Silver** (Bronze giữ raw): vi phạm trực tiếp yêu cầu (3) — Bronze là nơi incident
engineer đọc. Loại **bỏ hẳn body**: không còn incident review. Loại **mã hóa toàn bộ body bằng
khóa per-tenant**: người có quyền giải mã đọc được PII; tokenization chỉ thay span PII bằng
token (`<EMAIL:t_8f3a…>`), giữ ngữ cảnh để debug, và token chỉ giải được qua vault có audit.
Vault TTL 7 ngày nghĩa là sau 7 ngày token trở nên không thể đảo ngược ngay cả trong backup.

**D5 — Retention: drop partition theo ngày + `expire_snapshots` + `remove_orphan_files`, chạy
thành một job có kiểm chứng byte.**
Loại **S3 lifecycle rule xóa object > 7 ngày**: xóa file bên dưới một snapshot còn sống làm reader
lỗi `FileNotFound`, và metadata vẫn tham chiếu file đã mất. Loại **chỉ `DELETE WHERE ts < now-7d`**:
NB8 cho thấy dòng biến mất khỏi version hiện tại nhưng version cũ vẫn chứa nó; NB6 cho thấy expire
snapshot trên đường PyIceberg không xóa file vật lý (20 → 3 snapshot, avro 40 → 40). Job retention
phải: (a) drop partition, (b) expire snapshot cũ hơn 24 h, (c) orphan sweep với age guard,
(d) **đo byte dưới prefix ngày đó = 0** và ghi kết quả vào bảng audit.

**D6 — Gold: incremental MERGE vào `gold_tenant_5m`, p50/p95 bằng t-digest sketch.**
Loại **dashboard query thẳng Silver**: 2,000 dashboard × 12 lần/giờ × quét ~1B dòng/ngày là chi
phí compute không cần thiết. Loại **tính lại toàn bộ Gold mỗi 5 phút**: p95 không cộng dồn được,
nhưng t-digest thì merge được, nên chỉ cần MERGE cửa sổ mới + cửa sổ bị late data chạm tới
(`WHEN MATCHED AND src.window_end >= tgt.window_end`). Downsample sang `_1h` sau 30 ngày, `_1d`
sau 90 ngày để 1 năm aggregates vẫn nhỏ.

**D7 — Catalog: REST catalog (Lakekeeper hoặc Apache Polaris) làm điểm cấp quyền.**
Loại **Hive Metastore**: không có commit nguyên tử cho Iceberg multi-table và quyền theo table là
bolt-on. Loại **cấp quyền bằng IAM theo S3 prefix**: quyền ở mức file, không ở mức bảng/namespace;
không audit được "ai đọc Bronze". Với REST catalog + credential vending, role `incident_review`
là cách duy nhất đọc Bronze, mọi lần load table được log.

## 4. Failure modes (kịch bản 3 giờ sáng)

**F1 — Regression ở tokenizer làm lọt email vào Bronze** (tie với time travel / deletion, NB7–NB8).
*Detect:* job canary bơm 1 request/phút chứa PII tổng hợp đã biết (email, số điện thoại); job
scanner đọc Bronze mỗi 5 phút, nếu thấy chuỗi canary chưa bị token hóa → page on-call.
*Rollback:* (1) revoke grant `incident_review` trên catalog để không ai đọc thêm; (2) dùng
`snapshots` để tìm mọi snapshot từ thời điểm deploy; (3) rewrite các file bị ảnh hưởng
bằng `DELETE`/re-tokenize; (4) expire *ngay* các snapshot cũ (retain 0 cho riêng sự cố) và orphan
sweep — nếu không, time travel vẫn trả PII, đúng bài học NB8; (5) đo lại byte, ghi audit.
Kafka còn 6 h dữ liệu nên có thể replay qua tokenizer đã sửa.

**F2 — Compaction không chạy 3 đêm (job fail im lặng) → small-file explosion.**
*Detect:* metric từ `inspect.files()`: số file/partition, kích thước trung bình, và thời gian
`plan_files()` của query dashboard; alert khi avg file < 64 MB hoặc planning > 2 s.
*Rollback:* không cần rollback dữ liệu; chạy `rewrite_data_files` theo partition ngày cũ nhất
trước, tạm tăng commit interval lên 120 s để giảm file mới. Theo NB6, compaction ghi file mới
trước khi file cũ được dọn nên cần +1 ngày dung lượng tạm (đã tính trong mục 5).

**F3 — Deploy bảng giá sai làm `cost_usd` trong Gold lệch ×10.**
*Detect:* job đối soát hàng giờ so tổng `cost_usd` của Gold với tổng từ hệ thống billing; lệch
> 2 % → alert. *Rollback:* `rollback_to_snapshot` trên `gold_tenant_5m` về snapshot trước deploy
(C7), sửa bảng giá, recompute từ Silver. **Giới hạn quan trọng:** Silver chỉ giữ 7 ngày, nên lỗi
phát hiện sau 7 ngày **không thể tính lại** — vì vậy bảng giá được version hóa và `price_version`
được ghi vào từng dòng Gold để có thể hiệu chỉnh bằng phép nhân thay vì recompute.

**F4 — Upstream đổi schema** (`usage.input` → `usage.input_tokens`).
*Detect:* null-rate monitor trên Silver (`prompt_tokens IS NULL` > 0.1 % trong 5 phút).
*Rollback:* parser Silver đọc cả hai tên trong một bản deploy; Iceberg field-ID (NB5) cho phép
đổi tên cột Silver mà không rewrite; backfill các cửa sổ null từ Bronze (còn trong 7 ngày).

## 5. Ước lượng chi phí (back-of-envelope)

Giá giả định: S3 Standard **$0.023/GB-tháng**, PUT $0.005/1K, GET $0.0004/1K; EBS gp3 $0.08/GB-tháng;
EC2 c7g.4xlarge ~$0.58/giờ, r7g.2xlarge ~$0.43/giờ (on-demand, us-east-1, cần kiểm tra lại giá hiện hành).

| Hạng mục | Phép tính | $/tháng |
|---|---|---:|
| Bronze (tokenized body) | 5 TB/ngày ÷ 5 (zstd Parquet, giả định) = 1 TB/ngày × (7 + 1 ngày đệm compaction/retention) = 8 TB × $23/TB | 184 |
| Silver (metadata, không text) | ~60 B/req nén × 1B = 60 GB/ngày × 8 ngày = 0.48 TB × $23 | 11 |
| Gold 5m/1h/1d (1 năm) | ~30K cặp (tenant, model) hoạt động × 288 cửa sổ × ~40 B ≈ 0.35 GB/ngày, downsample sau 30 ngày → < 0.15 TB | 3 |
| Kafka buffer 6 h | 5 TB/ngày × 0.25 ÷ 4 (zstd) × RF 3 ≈ 0.94 TB × $80/TB | 75 |
| Metadata + snapshots | ~1 % data ở file 256–512 MB | 2 |
| Request S3 | PUT: 64 writer × 1,440 commit = 92K/ngày ≈ $14; GET: 2,000 dashboard × 288 lần/ngày × 30 × ~2 file ≈ 35M ≈ $14 | 28 |
| **Tổng storage** | | **≈ 303** |

Ngân sách $5K dư ~16×. Độ nhạy: nếu nén chỉ đạt 2× (body nhiều JSON ngẫu nhiên), Bronze thành
2.5 TB/ngày × 8 = 20 TB = $460, tổng ~$580 — vẫn dư. Kết luận dùng được trong review: **ngân
sách storage không phải lý do để giảm retention hay bỏ compaction**; nó cho phép giữ Kafka 6 h
để replay (F1) và một ngày đệm cho compaction.

Compute (không bị cap, nhưng cần nêu): tokenization giả định 2.5 ms CPU/req → trung bình
11.6K req/s × 2.5 ms ≈ 29 core, peak ≈ 88 core. Autoscale trung bình 4 × c7g.4xlarge (64 vCPU,
2× headroom) = 4 × $0.58 × 730 ≈ **$1,690**; compaction đêm (rewrite 1 TB/ngày trên spot)
≈ **$60**; Trino 3 × r7g.2xlarge cho dashboard ≈ **$940**. Compute ≈ $2.7K; cộng storage, tổng nền tảng ≈ **$3.0K/tháng**,
trong đó tokenization là khoản lớn nhất — đó là chỗ tối ưu đầu tiên (ví dụ chỉ chạy NER trên
span mà regex không chắc chắn).

## 6. MVP một tuần

**Slice:** 1 % traffic (≈ 10M req/ngày, chọn theo hash tenant) đi qua toàn bộ đường
Kafka → Flink (tokenize) → Bronze/Silver/Gold Iceberg → Trino → 1 dashboard tenant, kèm job
retention chạy với TTL rút ngắn **1 giờ** để thấy chu kỳ xóa trong tuần.

**Tiêu chí nghiệm thu (đo được):**
1. Freshness: p95 từ `ts` request tới lúc xuất hiện trong Gold ≤ 5 phút, đo bằng request canary
   có timestamp.
2. PII: 10,000 canary PII bơm vào → **0** chuỗi gốc tìm thấy trong Bronze/Silver/Gold (scanner
   quét toàn bộ, không lấy mẫu).
3. Đúng dữ liệu: số request trong Silver = số request duy nhất ở Kafka (dedup retry, như NB4:
   Bronze > Silver); tổng `cost_usd` Gold khớp tính tay trên một mẫu 1,000 request.
4. Small files: sau compaction đêm, kích thước file trung vị Bronze ≥ 128 MB.
5. Retention thật: sau TTL, `du` của prefix partition bị drop = **0 byte** và time travel về
   snapshot cũ báo lỗi (NB6/NB8: phải chứng minh byte biến mất, không chỉ dòng biến mất).
6. Đo hệ số nén thật và CPU/req thật để thay giả định ở mục 5.

**Cơ chế khó nhất cần kiểm chứng:** tiêu chí 2 và 5 cùng nhau — tokenization đủ nhanh ở peak và
xóa vật lý hoạt động đúng với snapshot/orphan của Iceberg. Nếu tiêu chí 5 thất bại trên engine
đã chọn, đó là tín hiệu dừng trước khi mở rộng lên 100 % traffic.

---

*Nguồn tham khảo:* notebook NB2, NB4–NB8 của lab này (số liệu đo trên máy cá nhân); tài liệu
Apache Iceberg về maintenance (`expire_snapshots`, `remove_orphan_files`, `rewrite_data_files`)
và Flink Iceberg sink; bảng giá AWS S3/EC2 công khai (giá trong bài là ước lượng, cần kiểm tra
lại tại thời điểm thiết kế).
